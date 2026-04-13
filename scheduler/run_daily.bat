@echo off
REM Financial Data Pipeline - Daily runner
REM 매일 오전 7시 실행 (Windows Task Scheduler 등록 후 자동 실행)

set PROJECT_DIR=D:\prosrc\AI\fine
set LOG_DIR=%PROJECT_DIR%\data\logs
set LOG_FILE=%LOG_DIR%\pipeline_%date:~0,4%%date:~5,2%%date:~8,2%.log

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo [%date% %time%] Pipeline start >> "%LOG_FILE%"

REM 가상환경 활성화 (존재하는 경우)
if exist "%PROJECT_DIR%\.venv\Scripts\activate.bat" (
    call "%PROJECT_DIR%\.venv\Scripts\activate.bat"
) else if exist "%PROJECT_DIR%\venv\Scripts\activate.bat" (
    call "%PROJECT_DIR%\venv\Scripts\activate.bat"
)

cd /d "%PROJECT_DIR%"

REM 일간 리포트 실행
python main.py --mode daily >> "%LOG_FILE%" 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] Pipeline FAILED (exit code %errorlevel%) >> "%LOG_FILE%"
    exit /b %errorlevel%
)

echo [%date% %time%] Pipeline done >> "%LOG_FILE%"
