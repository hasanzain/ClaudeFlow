import json
import os
import shutil
import platform
import subprocess
import sys
from pathlib import Path


def get_claude_desktop_config_paths() -> list[Path]:
    """Mengembalikan lokasi konfigurasi claude_desktop_config.json sesuai OS."""
    system = platform.system()
    paths: list[Path] = []
    if system == "Windows":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        localappdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        paths.append(Path(appdata) / "Claude" / "claude_desktop_config.json")
        paths.append(Path(localappdata) / "Claude-3p" / "claude_desktop_config.json")
        paths.append(Path(appdata) / "Claude-3p" / "claude_desktop_config.json")
    elif system == "Darwin":
        paths.append(Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json")
        paths.append(Path.home() / "Library" / "Application Support" / "Claude-3p" / "claude_desktop_config.json")
    else:
        paths.append(Path.home() / ".config" / "Claude" / "claude_desktop_config.json")
        paths.append(Path.home() / ".config" / "Claude-3p" / "claude_desktop_config.json")
    return paths


def get_claude_code_config_path() -> Path:
    """Mengembalikan lokasi file global konfigurasi Claude Code (~/.claude.json)."""
    return Path.home() / ".claude.json"


def get_global_skill_dir() -> Path:
    """Mengembalikan direktori global skill Claude (~/.claude/skills/)."""
    return Path.home() / ".claude" / "skills"


def main():
    project_root = Path(__file__).resolve().parent
    print("=" * 65)
    print("  ClaudeFlow — 1-Click Automated Setup (MCP & Skill)")
    print(f"  Project Root: {project_root}")
    print("=" * 65)

    # 1. Setup Virtual Environment
    venv_dir = project_root / "venv"
    if not venv_dir.exists():
        print("\n[1/5] Membuat Python Virtual Environment (venv)...")
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
    else:
        print("\n[1/5] Virtual Environment yang ada ditemukan.")

    if platform.system() == "Windows":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    if not venv_python.exists():
        print(f"ERROR: Python binary di venv tidak ditemukan di {venv_python}")
        sys.exit(1)

    # 2. Install Dependensi
    print("\n[2/5] Menginstal dependensi dari requirements.txt...")
    req_file = project_root / "requirements.txt"
    subprocess.check_call([
        str(venv_python), "-m", "pip", "install", "-r", str(req_file), "--quiet"
    ])

    # 3. Install Playwright Chromium
    print("\n[3/5] Memastikan Playwright Chromium terinstal...")
    try:
        subprocess.check_call([
            str(venv_python), "-m", "playwright", "install", "chromium"
        ])
    except Exception as exc:
        print(f"Catatan instalasi Playwright: {exc}")

    # 4. Registrasi MCP Server
    print("\n[4/5] Mendaftarkan 'claudeflow' MCP Server...")
    server_script = project_root / "server.py"

    # A. Registrasi ke ~/.claude.json (Claude Code / Desktop Code tab)
    claude_code_cfg = get_claude_code_config_path()
    if claude_code_cfg.exists():
        try:
            cfg_data = json.loads(claude_code_cfg.read_text(encoding="utf-8"))
            mcp_servers = cfg_data.setdefault("mcpServers", {})
            mcp_servers["claudeflow"] = {
                "type": "stdio",
                "command": str(venv_python).replace("\\", "/"),
                "args": [str(server_script).replace("\\", "/")],
                "env": {}
            }
            claude_code_cfg.write_text(json.dumps(cfg_data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"-> Berhasil didaftarkan ke Claude Code config: {claude_code_cfg}")
        except Exception as e:
            print(f"Gagal memperbarui ~/.claude.json: {e}")

    # B. Registrasi ke claude_desktop_config.json (Claude Desktop App)
    desktop_configs = get_claude_desktop_config_paths()
    for cfg_p in desktop_configs:
        if cfg_p.exists() or cfg_p.parent.exists():
            cfg_p.parent.mkdir(parents=True, exist_ok=True)
            cfg_data = {}
            if cfg_p.exists():
                try:
                    cfg_data = json.loads(cfg_p.read_text(encoding="utf-8"))
                except Exception:
                    cfg_data = {}
            mcp_srv = cfg_data.setdefault("mcpServers", {})
            mcp_srv["claudeflow"] = {
                "command": str(venv_python),
                "args": [str(server_script)]
            }
            cfg_p.write_text(json.dumps(cfg_data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"-> Berhasil didaftarkan ke Claude Desktop config: {cfg_p}")

    # 5. Instalasi Global Skill: claudeflow-operator
    print("\n[5/5] Memasang Skill 'claudeflow-operator' ke direktori global Claude...")
    source_skill = project_root / ".claude" / "skills" / "claudeflow-operator"
    target_skill_dir = get_global_skill_dir() / "claudeflow-operator"

    if source_skill.exists():
        target_skill_dir.mkdir(parents=True, exist_ok=True)
        for item in source_skill.iterdir():
            if item.is_file():
                shutil.copy2(item, target_skill_dir / item.name)
        print(f"-> Skill terpasang di: {target_skill_dir}")
    else:
        print("Folder skill lokal tidak ditemukan.")

    print("\n" + "=" * 65)
    print("  [SUKSES] ClaudeFlow MCP dan Skill berhasil dipasang!")
    print(f"  MCP Server : claudeflow ({server_script})")
    print(f"  Skill Name : claudeflow-operator")
    print("  Tindakan   : Restart Claude Desktop / Claude Code untuk memuat MCP.")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
