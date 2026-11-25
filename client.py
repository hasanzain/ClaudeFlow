import time
import base64
import re
from pathlib import Path
from dataclasses import dataclass, field
from config import FLOW_URL, PROFILES_DIR

class AuthError(Exception):
    """Token atau session Google kedaluwarsa."""
    pass

class RateLimitError(Exception):
    """Batas kuota habis / HTTP 429."""
    pass

class InsufficientCreditsError(Exception):
    """Saldo kredit akun tidak mencukupi untuk job ini."""
    def __init__(self, message: str, available_credits: int | None = None, required_credits: int | None = None):
        super().__init__(message)
        self.available_credits = available_credits
        self.required_credits = required_credits

class RpcError(Exception):
    """Error eksekusi dari Google server."""
    pass

@dataclass
class GenerationResult:
    job_id: str
    status: str
    media_url: str | None
    output_path: Path | None
    output_paths: list[Path] = field(default_factory=list)
    media_assets: list[dict] = field(default_factory=list)
    error: str | None = None

class FlowRpcClient:
    """Client eksekutor Google Flow dengan native browser profile."""
    def __init__(self, account_id: str, profile_dir: Path | str | None = None, cookies: dict | None = None, proxy: str | None = None, mock: bool = False):
        self.account_id = account_id
        self.profile_dir = Path(profile_dir) if profile_dir else (PROFILES_DIR / account_id)
        self.cookies = cookies or {}
        self.proxy = proxy
        self.mock = mock

    def generate(self, prompt: str, media_type: str = "image", aspect_ratio: str | None = None, model: str | None = None, count: int | None = None, reference_asb_ids: list[str] | None = None, project_name: str | None = None, project_id: str | None = None, dest_file: Path | None = None) -> GenerationResult:
        if self.mock:
            # ponytail: mock simulator ceiling dev environment, upgrade to live RPC
            time.sleep(1)
            num_outputs = count or 1
            out_paths = []
            mock_assets = []
            if dest_file:
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                for idx in range(num_outputs):
                    p = dest_file if num_outputs == 1 else dest_file.with_name(f"{dest_file.stem}_{idx+1}{dest_file.suffix}")
                    p.write_text(f"Mock generated {media_type} (proj={project_name}, aspect={aspect_ratio}, model={model}, count={count}, item={idx+1}) for prompt: {prompt}\n", encoding="utf-8")
                    out_paths.append(p)
                    mock_assets.append({"path": str(p), "asb_id": f"mock_asb_id_{idx+1}"})
            return GenerationResult(
                job_id=f"mock_{int(time.time())}",
                status="COMPLETED",
                media_url="https://mock.flow.google.com/sample.mp4",
                output_path=out_paths[0] if out_paths else dest_file,
                output_paths=out_paths,
                media_assets=mock_assets
            )

        from playwright.sync_api import sync_playwright

        if not self.profile_dir.exists():
            raise AuthError(f"Profile directory untuk akun '{self.account_id}' belum ada. Jalankan: python login_helper.py {self.account_id}")

        dest_file = dest_file or Path(f"outputs/gen_{int(time.time())}.{'mp4' if media_type == 'video' else 'webp'}")
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            launch_args = {
                "user_data_dir": str(self.profile_dir),
                "headless": True,
                "args": ["--disable-blink-features=AutomationControlled"]
            }
            if self.proxy:
                launch_args["proxy"] = {"server": self.proxy}

            try:
                ctx = p.chromium.launch_persistent_context(**launch_args, channel="msedge")
            except Exception:
                ctx = p.chromium.launch_persistent_context(**launch_args)

            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()

                # Resolve project_id dari project_manager jika project_name sudah terdaftar
                if project_name and not project_id:
                    from project_manager import ProjectManager
                    saved_proj = ProjectManager().get_project(project_name)
                    if saved_proj:
                        project_id = saved_proj.get("id")

                # Navigasi ke project spesifik atau ke Flow beranda
                if project_id:
                    target_url = f"{FLOW_URL}/project/{project_id}"
                    page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2000)
                else:
                    page.goto(FLOW_URL, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2000)

                # Cek jika dialihkan ke halaman login
                if "accounts.google.com" in page.url:
                    raise AuthError(f"Session akun '{self.account_id}' expired. Silakan login ulang.")

                # Jika belum di dalam canvas project
                if "/project/" not in page.url:
                    if project_name:
                        # Buat project baru dengan nama yang diminta
                        new_btn = page.locator('button:has-text("Project baru")').first
                        if new_btn.count() > 0:
                            new_btn.click()
                            page.wait_for_timeout(3000)
                        else:
                            raise RpcError("Tombol 'Project baru' tidak ditemukan di Flow beranda.")
                    else:
                        # Masuk ke project yang sudah ada atau buat baru
                        proj_link = page.locator('a[href^="/project/"]').first
                        if proj_link.count() > 0:
                            proj_link.click()
                            page.wait_for_timeout(2000)
                        else:
                            new_btn = page.locator('button:has-text("Project baru")').first
                            if new_btn.count() > 0:
                                new_btn.click()
                                page.wait_for_timeout(2000)
                            else:
                                raise RpcError("Tidak dapat menemukan project Flow aktif atau tombol Project baru.")

                # Tunggu canvas aktif
                page.wait_for_selector('button[aria-label="Mulai pembuatan"]', timeout=25000)

                # Jika ada permintaan project_name, ganti judul project di kanvas dan simpan ke ProjectManager
                if project_name:
                    try:
                        title_span = page.locator('.header-title').first
                        if title_span.count() > 0 and title_span.inner_text().strip() != project_name:
                            title_span.click()
                            page.wait_for_timeout(400)
                            inp = page.locator('input.editable-text-input').first
                            if inp.count() > 0 and inp.is_visible():
                                inp.fill(project_name)
                                inp.press("Enter")
                                page.wait_for_timeout(600)

                        # Ambil ID project dari URL saat ini dan daftarkan ke project_manager
                        cur_url = page.url
                        if "/project/" in cur_url:
                            pid = cur_url.split("/project/")[1].split("/")[0].split("?")[0]
                            from project_manager import ProjectManager
                            ProjectManager().register_project(pid, project_name, account_id=self.account_id)
                    except Exception:
                        pass

                # 1. Pastikan selalu menggunakan MODE KLASIK (matikan Agen Flow jika aktif)
                try:
                    agent_toggle = page.locator('button[aria-label="Agen Flow"]').first
                    if agent_toggle.count() > 0 and 'checked' in (agent_toggle.get_attribute('class') or ''):
                        agent_toggle.click()
                        page.wait_for_timeout(700)
                except Exception as e:
                    print(f"[Client] Warning disabling agent mode: {e}")

                # 2. Cek saldo kredit akun yang tersedia
                available_credits = None
                try:
                    user_btn = page.locator('.header-user-button, [aria-label*="Detail akun"]').first
                    if user_btn.count() > 0:
                        user_btn.click()
                        page.wait_for_timeout(800)
                        menu_text = page.locator('.cdk-overlay-container').inner_text()
                        m_cred = re.search(r'(\d+)\s+kredit', menu_text)
                        if m_cred:
                            available_credits = int(m_cred.group(1))
                            from accounts import AccountManager
                            AccountManager().update_credits(self.account_id, available_credits)
                            print(f"[Client] Akun {self.account_id} memiliki {available_credits} kredit tersedia.")

                        # Tutup menu profil akun
                        close_btn = page.locator('.cdk-overlay-container button:has-text("Tutup"), .cdk-overlay-backdrop').first
                        if close_btn.count() > 0:
                            close_btn.click()
                        else:
                            page.keyboard.press("Escape")
                        page.wait_for_timeout(500)
                except Exception as e:
                    print(f"[Client] Warning checking available credits: {e}")

                # 3. Atur parameter generasi di Mode Klasik via 'Pemicu setelan'
                required_credits = 0
                try:
                    pemicu = page.locator('button[aria-label="Pemicu setelan"]').first
                    if pemicu.count() > 0:
                        pemicu.click()
                        page.wait_for_timeout(700)

                        # A. Pilih Gambar atau Video
                        target_type = "Video" if media_type == "video" else "Gambar"
                        type_btn = page.locator(f'.cdk-overlay-container button:has-text("{target_type}")').first
                        if type_btn.count() > 0:
                            type_btn.click()
                            page.wait_for_timeout(300)

                        # B. Pilih Rasio Aspek
                        if aspect_ratio:
                            ar_btn = page.locator(f'.cdk-overlay-container button:has-text("{aspect_ratio}")').first
                            if ar_btn.count() > 0:
                                ar_btn.click()
                                page.wait_for_timeout(300)

                        # C. Pilih Model jika diberikan
                        if model:
                            m_btn = page.locator(f'.cdk-overlay-container button:has-text("{model}")').first
                            if m_btn.count() > 0:
                                m_btn.click()
                                page.wait_for_timeout(300)

                        # D. Pilih Jumlah Variasi Output (x1, x2, x3, x4)
                        if count:
                            c_btn = page.locator(f'.cdk-overlay-container button:has-text("x{count}")').first
                            if c_btn.count() > 0:
                                c_btn.click()
                                page.wait_for_timeout(300)

                        # E. Hitung estimasi kredit yang diperlukan
                        ov_text = page.locator('.cdk-overlay-container').inner_text()
                        m_cost = re.search(r'Pembuatan akan menggunakan\s+(\d+)\s+kredit', ov_text)
                        if m_cost:
                            required_credits = int(m_cost.group(1))
                            print(f"[Client] Biaya estimasi pembuatan: {required_credits} kredit.")

                        page.keyboard.press("Escape")
                        page.wait_for_timeout(400)
                except Exception as e:
                    print(f"[Client] Warning setting classic parameters: {e}")
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(300)

                # 4. Validasi pra-eksekusi saldo kredit
                if available_credits is not None and required_credits > available_credits:
                    raise InsufficientCreditsError(
                        f"Kredit tidak cukup: Saldo {available_credits} kredit < Diperlukan {required_credits} kredit.",
                        available_credits=available_credits,
                        required_credits=required_credits
                    )

                # Ambil daftar gambar/video awal
                existing_media = page.evaluate(r'''() => {
                    const cleanId = (url) => {
                        const m = url.match(/\/asb\/([^=?]+)/);
                        return m ? m[1] : url;
                    };
                    return Array.from(document.querySelectorAll('img, video'))
                        .map(i => i.src)
                        .filter(s => s && s.includes('asb'))
                        .map(cleanId);
                }''')

                # Jika ada reference_asb_ids, pilih aset gambar dari library proyek via tombol Tambahkan bahan
                if reference_asb_ids:
                    for ref_id in reference_asb_ids:
                        try:
                            add_btn = page.locator('button[aria-label*="Tambahkan bahan"]').first
                            if add_btn.count() > 0:
                                add_btn.click()
                                page.wait_for_timeout(1000)

                                clicked = page.evaluate('''(tid) => {
                                    const dialog = document.querySelector('.cdk-overlay-container') || document.body;
                                    const img = Array.from(dialog.querySelectorAll('img')).find(i => i.src && i.src.includes(tid));
                                    if (img) {
                                        const btn = img.closest('button.asset-item') || img.closest('button');
                                        if (btn) {
                                            btn.click();
                                            return true;
                                        }
                                    }
                                    return false;
                                }''', ref_id)

                                if clicked:
                                    page.wait_for_timeout(500)
                                    btn_add = page.locator('button.detail-add-to-prompt-btn').first
                                    if btn_add.count() > 0 and btn_add.is_enabled():
                                        btn_add.click()
                                        page.wait_for_timeout(800)
                                else:
                                    # Tutup dialog jika tidak ditemukan
                                    page.keyboard.press("Escape")
                                    page.wait_for_timeout(300)
                        except Exception as e:
                            print(f"[Client] Warning adding reference asset {ref_id}: {e}")
                            page.keyboard.press("Escape")

                expected_count = count or 1

                # Isi prompt ke box input
                prompt_box = page.locator('[aria-label="Apa yang ingin Anda buat?"]').first
                prompt_box.click()
                prompt_box.fill(prompt)
                page.wait_for_timeout(500)

                # Submit prompt (klik tombol submit atau tekan Enter)
                gen_btn = page.locator('button[aria-label="Mulai pembuatan"]').first
                if gen_btn.count() > 0 and gen_btn.is_enabled():
                    gen_btn.click()
                else:
                    prompt_box.press("Enter")

                # Tunggu proses generasi selesai
                # Deteksi 1: Muncul tombol 'Hentikan' lalu tunggu sampai hilang
                try:
                    page.locator('button:has-text("Hentikan")').first.wait_for(state="attached", timeout=6000)
                    page.locator('button:has-text("Hentikan")').first.wait_for(state="detached", timeout=180000)
                except Exception:
                    pass

                # Deteksi 2: Tunggu media baru muncul di canvas / chat (polling hingga 60 detik)
                for _ in range(30):
                    has_new = page.evaluate(r'''(params) => {
                        const beforeSet = new Set(params.beforeIds || []);
                        const cleanId = (url) => {
                            const m = url.match(/\/asb\/([^=?]+)/);
                            return m ? m[1] : url;
                        };
                        const imgs = Array.from(document.querySelectorAll('img, video'))
                            .map(i => i.src)
                            .filter(s => s && s.includes('asb'));
                        return imgs.some(s => !beforeSet.has(cleanId(s)));
                    }''', {"beforeIds": existing_media})
                    if has_new:
                        page.wait_for_timeout(3000)
                        break
                    page.wait_for_timeout(2000)

                # Cek error kuota / rate limit
                dialog_text = ""
                for m in page.locator('[role="dialog"], mat-dialog-container, .cdk-overlay-pane').all():
                    txt = m.inner_text().strip()
                    if txt:
                        dialog_text += " " + txt

                if any(w in dialog_text.lower() for w in ["kuota", "quota", "limit", "terlalu banyak", "try again later"]):
                    raise RateLimitError(f"Google Flow kuota habis / rate limited: {dialog_text[:100]}")

                # Ambil media hasil terbaru (coba hingga 15 detik jika media sedang render ke canvas)
                media_list = []
                for _ in range(15):
                    raw_items = page.evaluate(r'''(params) => {
                        const beforeSet = new Set(params.beforeIds || []);
                        const cleanId = (url) => {
                            const m = url.match(/\/asb\/([^=?]+)/);
                            return m ? m[1] : url;
                        };
                        const allImgs = Array.from(document.querySelectorAll('img, video'))
                            .map(i => i.src)
                            .filter(s => s && s.includes('asb'));

                        // Filter hanya item yang baru muncul
                        let newUrls = allImgs.filter(s => !beforeSet.has(cleanId(s)));
                        if (newUrls.length === 0 && allImgs.length > 0) {
                            newUrls = [allImgs[0]];
                        }

                        // Buat daftar unik
                        const seen = new Set();
                        const uniqueTargets = [];
                        for (const u of newUrls) {
                            const cid = cleanId(u);
                            if (!seen.has(cid)) {
                                seen.add(cid);
                                let full = u;
                                if (full.includes('=s')) {
                                    full = full.replace(/=s\d+[^?]*/, '=s1600-rw');
                                }
                                uniqueTargets.push({ fullUrl: full, origUrl: u, asbId: cid });
                            }
                            if (uniqueTargets.length >= params.maxCount) break;
                        }

                        if (uniqueTargets.length === 0) return Promise.resolve([]);

                        return Promise.all(uniqueTargets.map(t => {
                            return fetch(t.fullUrl)
                                .then(res => res.blob())
                                .then(blob => new Promise(resolve => {
                                    const reader = new FileReader();
                                    reader.onloadend = () => resolve({url: t.fullUrl, asbId: t.asbId, data: reader.result, size: blob.size});
                                    reader.readAsDataURL(blob);
                                }))
                                .catch(() => {
                                    return fetch(t.origUrl)
                                        .then(r => r.blob())
                                        .then(b => new Promise(res => {
                                            const reader = new FileReader();
                                            reader.onloadend = () => res({url: t.origUrl, asbId: t.asbId, data: reader.result, size: b.size});
                                            reader.readAsDataURL(b);
                                        }))
                                        .catch(() => null);
                                });
                        }));
                    }''', {"beforeIds": existing_media, "maxCount": expected_count})

                    if raw_items and any(item and item.get("data") for item in raw_items):
                        media_list = [item for item in raw_items if item and item.get("data")]
                        break
                    page.wait_for_timeout(1000)

                if not media_list:
                    raise RpcError("Generasi selesai tapi media output tidak ditemukan di canvas.")

                saved_paths = []
                media_assets = []
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                for idx, m in enumerate(media_list):
                    target_dest = dest_file if len(media_list) == 1 else dest_file.with_name(f"{dest_file.stem}_{idx+1}{dest_file.suffix}")
                    header, b64_str = m["data"].split(",", 1)
                    target_dest.write_bytes(base64.b64decode(b64_str))
                    saved_paths.append(target_dest)
                    media_assets.append({
                        "path": str(target_dest),
                        "asb_id": m.get("asbId"),
                        "url": m.get("url")
                    })

                return GenerationResult(
                    job_id=f"flow_{int(time.time())}",
                    status="COMPLETED",
                    media_url=media_list[0].get("url"),
                    output_path=saved_paths[0],
                    output_paths=saved_paths,
                    media_assets=media_assets
                )

            finally:
                ctx.close()

if __name__ == "__main__":
    client = FlowRpcClient("test_mock", mock=True)
    out = Path("outputs/test_mock_check.png")
    res = client.generate("test prompt", media_type="image", count=2, dest_file=out)
    assert res.status == "COMPLETED"
    assert len(res.output_paths) == 2
    for p in res.output_paths:
        assert p.exists()
        p.unlink(missing_ok=True)
    out.unlink(missing_ok=True)
    print("FlowRpcClient self-check passed.")
