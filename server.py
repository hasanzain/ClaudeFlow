import json
import time
from typing import Any, Dict, List, Optional
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from config import JOBS_DIR, OUTPUTS_DIR
from accounts import AccountManager
from project_manager import ProjectManager
from daemon import QueueDaemon

mcp = FastMCP("claudeflow")

@mcp.tool()
def list_accounts() -> Dict[str, Any]:
    """Menampilkan daftar semua akun Google Flow terdaftar, statusnya (READY/COOLDOWN), dan ketersediaan session browser."""
    mgr = AccountManager()
    accounts = []
    for a in mgr.accounts:
        accounts.append({
            "id": a.id,
            "email": a.email,
            "status": a.status,
            "cooldown_until": a.cooldown_until,
            "has_profile": a.profile_dir.exists(),
            "proxy": a.proxy
        })
    return {"accounts": accounts, "total": len(accounts)}

@mcp.tool()
def add_account(account_id: str, email: str, proxy: Optional[str] = None) -> Dict[str, Any]:
    """Mendaftarkan akun Google baru ke pool ClaudeFlow.

    Args:
        account_id: ID unik akun (misal: acc1, akun_cadangan)
        email: Alamat email Google
        proxy: Proxy opsional (http://user:pass@host:port)
    """
    mgr = AccountManager()
    acc = mgr.add_account(account_id, email, proxy)
    return {
        "success": True,
        "message": f"Akun {acc.id} ({acc.email}) berhasil ditambahkan. Jalankan login_helper untuk login pertama kali.",
        "account": {"id": acc.id, "email": acc.email}
    }

@mcp.tool()
def list_projects() -> Dict[str, Any]:
    """Menampilkan daftar kanvas project Google Flow yang tersimpan di registry lokal."""
    pm = ProjectManager()
    projects = pm.list_projects()
    return {"projects": projects}

@mcp.tool()
def generate_media(
    prompt: str,
    media_type: str = "image",
    aspect_ratio: Optional[str] = None,
    model: Optional[str] = None,
    count: Optional[int] = None,
    reference_asb_ids: Optional[List[str]] = None,
    project_name: Optional[str] = None,
    project_id: Optional[str] = None,
    wait_for_completion: bool = True,
    timeout_seconds: int = 180
) -> Dict[str, Any]:
    """Menjalankan generasi gambar/video Google Flow secara otomatis via queue daemon.

    Args:
        prompt: Teks perintah generasi visual.
        media_type: 'image' atau 'video' (default: 'image').
        aspect_ratio: Rasio aspek: '16:9', '4:3', '1:1', '3:4', atau '9:16'.
        model: Nama model Flow (misal: 'Nano Banana 2.1', 'Veo 3.1 - Lite').
        count: Jumlah output variasi dalam 1x generate (1, 2, 3, atau 4).
        reference_asb_ids: Daftar ASB ID gambar di kanvas untuk konsistensi karakter/gaya visual tanpa duplikasi aset.
        project_name: Nama project cerita (hasil disimpan di folder outputs/<project_name>/).
        project_id: ID project kanvas Google Flow spesifik (opsional).
        wait_for_completion: Menunggu sampai job selesai dan mengembalikan path file serta ASB ID (default: True).
        timeout_seconds: Waktu tunggu maksimal jika wait_for_completion=True (default: 180 detik).
    """
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    job_id = f"job_{int(time.time() * 1000)}"
    job_path = JOBS_DIR / f"{job_id}.json"

    job_data = {
        "id": job_id,
        "prompt": prompt,
        "type": media_type,
        "aspect_ratio": aspect_ratio,
        "model": model,
        "count": count,
        "reference_asb_ids": reference_asb_ids,
        "project_name": project_name,
        "project_id": project_id,
        "created_at": time.time()
    }

    job_path.write_text(json.dumps(job_data, indent=2, ensure_ascii=False), encoding="utf-8")

    if not wait_for_completion:
        return {
            "job_id": job_id,
            "status": "QUEUED",
            "message": "Job dimasukkan ke antrean. Pantau file .done untuk hasilnya."
        }

    # Jalankan daemon processor satu putaran langsung jika background daemon tidak aktif
    daemon = QueueDaemon()
    start_time = time.time()
    done_file = JOBS_DIR / f"{job_id}.done"
    failed_file = JOBS_DIR / f"{job_id}.failed"

    while (time.time() - start_time) < timeout_seconds:
        if done_file.exists():
            data = json.loads(done_file.read_text(encoding="utf-8"))
            return {
                "success": True,
                "job_id": job_id,
                "status": "COMPLETED",
                "outputs": data.get("outputs", []),
                "media_assets": data.get("media_assets", []),
                "account_used": data.get("account_used")
            }
        if failed_file.exists():
            data = json.loads(failed_file.read_text(encoding="utf-8"))
            return {
                "success": False,
                "job_id": job_id,
                "status": "FAILED",
                "error": data.get("error", "Unknown error")
            }

        # Proses job jika worker utama belum mengambilnya
        processed = daemon.process_once()
        if processed == 0:
            time.sleep(2)

    return {
        "success": False,
        "job_id": job_id,
        "status": "TIMEOUT",
        "error": f"Generasi melebihi batas waktu {timeout_seconds}s."
    }

@mcp.tool()
def get_job_status(job_id: str) -> Dict[str, Any]:
    """Memeriksa status job spesifik berdasarkan job_id."""
    done_file = JOBS_DIR / f"{job_id}.done"
    failed_file = JOBS_DIR / f"{job_id}.failed"
    queued_file = JOBS_DIR / f"{job_id}.json"

    if done_file.exists():
        data = json.loads(done_file.read_text(encoding="utf-8"))
        return {"job_id": job_id, "status": "COMPLETED", "result": data}
    elif failed_file.exists():
        data = json.loads(failed_file.read_text(encoding="utf-8"))
        return {"job_id": job_id, "status": "FAILED", "error": data}
    elif queued_file.exists():
        return {"job_id": job_id, "status": "QUEUED"}
    else:
        return {"job_id": job_id, "status": "NOT_FOUND"}

if __name__ == "__main__":
    mcp.run()
