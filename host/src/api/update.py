"""
api/update.py
==============
クライアントアップデート配布 API エンドポイント。

エンドポイント:
  GET /api/update/info?current=VERSION  - 最新バージョン情報を返す (後方互換)
  GET /api/update/tauri                 - Tauri updater 向けバージョン情報を返す
  GET /api/update/download/{filename}   - インストーラーファイルをダウンロードする

配布ファイルの配置:
  host/client_dist/version.json  : バージョン情報 (開発者が更新する)
  host/client_dist/*.exe         : NSIS インストーラー本体

version.json の形式:
  {
    "version": "1.2.3",
    "release_notes": "変更点の説明",
    "pub_date": "2026-03-18T00:00:00Z",
    "windows": {
      "filename": "BSApp_1.2.3_x64-setup.exe",
      "url": "/api/update/download/BSApp_1.2.3_x64-setup.exe",
      "signature": "<npm run tauri signer sign で生成した .sig ファイルの内容>"
    }
  }
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from ..models import UpdateInfoResponse

router = APIRouter()

# host/client_dist/ ディレクトリ (このファイルの3階層上 = host/)
_DIST_DIR = Path(__file__).resolve().parents[2] / "client_dist"


def _compare_versions(v1: str, v2: str) -> int:
    """v1 > v2 なら 1、v1 == v2 なら 0、v1 < v2 なら -1 を返す。"""
    try:
        p1 = [int(x) for x in v1.split(".")]
        p2 = [int(x) for x in v2.split(".")]
        # 短い方をゼロ埋めして比較
        length = max(len(p1), len(p2))
        p1 += [0] * (length - len(p1))
        p2 += [0] * (length - len(p2))
        for a, b in zip(p1, p2):
            if a > b:
                return 1
            if a < b:
                return -1
        return 0
    except ValueError:
        return 0


@router.get("/info", response_model=UpdateInfoResponse)
def get_update_info(current: str = "0.0.0", platform: str = "windows") -> UpdateInfoResponse:
    """最新バージョン情報を返す。

    Parameters
    ----------
    current : str
        クライアントの現在のバージョン (例: "1.0.0")
    platform : str
        プラットフォーム。"windows" または "linux" (デフォルト: "windows")
    """
    version_file = _DIST_DIR / "version.json"
    if not version_file.exists():
        # version.json がない場合は「アップデートなし」を返す
        return UpdateInfoResponse(
            latest_version=current,
            current_version=current,
            has_update=False,
        )

    data = json.loads(version_file.read_text(encoding="utf-8"))
    latest = str(data.get("version", current))
    has_update = _compare_versions(latest, current) > 0

    plat_info = data.get(platform, data.get("windows", {}))
    filename = plat_info.get("filename", "")
    download_url = plat_info.get("url", "")

    return UpdateInfoResponse(
        latest_version=latest,
        current_version=current,
        has_update=has_update,
        release_notes=str(data.get("release_notes", "")),
        download_url=download_url,
        filename=filename,
    )


@router.get("/tauri")
def get_tauri_update(request: Request) -> JSONResponse:
    """Tauri updater プロトコル準拠のバージョン情報を返す。

    Tauri updater は GET リクエストに `Accept: application/json` を付けて呼び出す。
    アップデートがない場合は 204 No Content を返す。
    """
    version_file = _DIST_DIR / "version.json"
    if not version_file.exists():
        return JSONResponse(status_code=204, content=None)

    data = json.loads(version_file.read_text(encoding="utf-8"))
    latest = str(data.get("version", "0.0.0"))

    win_info = data.get("windows", {})
    filename = win_info.get("filename", "")
    signature = win_info.get("signature", "")
    rel_url = win_info.get("url", "")

    if not filename or not signature or not rel_url:
        return JSONResponse(status_code=204, content=None)

    # 絶対 URL に変換 (ホスト名はリクエストから取得)
    base = str(request.base_url).rstrip("/")
    download_url = f"{base}{rel_url}"

    pub_date = data.get("pub_date", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    return JSONResponse(content={
        "version": latest,
        "notes": data.get("release_notes", ""),
        "pub_date": pub_date,
        "platforms": {
            "windows-x86_64": {
                "url": download_url,
                "signature": signature,
            }
        },
    })


@router.get("/download/{filename}")
def download_file(filename: str) -> FileResponse:
    """インストーラーファイルをダウンロードする。

    パストラバーサル対策: ファイル名にパス区切り文字が含まれる場合は 400 エラー。
    """
    # パストラバーサル防止
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = _DIST_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )
