"""
Windows Task Scheduler 등록 스크립트.

Usage:
    python scheduler/setup_task.py [--hour 7] [--minute 0] [--unregister]

실행 후 작업 스케줄러에서 'FinancialDataPipeline' 작업으로 확인 가능.
관리자 권한 없이도 현재 사용자 계정으로 등록된다.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TASK_NAME = "FinancialDataPipeline"
PROJECT_DIR = Path(__file__).parent.parent.resolve()
BAT_FILE = PROJECT_DIR / "scheduler" / "run_daily.bat"


def register(hour: int = 7, minute: int = 0) -> None:
    """매일 지정 시각에 파이프라인을 실행하는 Task Scheduler 작업 등록."""
    start_time = f"{hour:02d}:{minute:02d}"
    cmd = [
        "schtasks", "/Create",
        "/TN", TASK_NAME,
        "/TR", str(BAT_FILE),
        "/SC", "DAILY",
        "/ST", start_time,
        "/RL", "HIGHEST",      # 높은 권한
        "/F",                  # 기존 작업 덮어쓰기
    ]
    print(f"작업 등록: {TASK_NAME} @ {start_time} 매일")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("등록 완료.")
        print(f"배치 파일: {BAT_FILE}")
        print(f"로그 위치: {PROJECT_DIR / 'data' / 'logs'}")
    else:
        print(f"등록 실패:\n{result.stderr}", file=sys.stderr)
        sys.exit(result.returncode)


def unregister() -> None:
    """등록된 작업 삭제."""
    cmd = ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"작업 삭제 완료: {TASK_NAME}")
    else:
        print(f"삭제 실패:\n{result.stderr}", file=sys.stderr)
        sys.exit(result.returncode)


def status() -> None:
    """등록된 작업 상태 조회."""
    cmd = ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"작업 없음 또는 조회 실패: {TASK_NAME}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Task Scheduler 등록/삭제")
    parser.add_argument("--hour",       type=int, default=7,     help="실행 시각 (시, 기본 7)")
    parser.add_argument("--minute",     type=int, default=0,     help="실행 시각 (분, 기본 0)")
    parser.add_argument("--unregister", action="store_true",     help="작업 삭제")
    parser.add_argument("--status",     action="store_true",     help="작업 상태 조회")
    args = parser.parse_args()

    if args.unregister:
        unregister()
    elif args.status:
        status()
    else:
        register(args.hour, args.minute)
