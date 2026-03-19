@echo off
setlocal enabledelayedexpansion

REM =====================================================
REM BSApp - Company DB Debug Helper
REM Windows local PostgreSQL / FastAPI startup investigation
REM =====================================================

set "SCRIPT_DIR=%~dp0"
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"
set "HOST_DIR=!SCRIPT_DIR!\host"
set "ENV_FILE=!HOST_DIR!\.env"
set "LOG_FILE=!SCRIPT_DIR!\debug-company-db-result.txt"

echo ===================================================== > "!LOG_FILE!"
echo BSApp Company DB Debug Result >> "!LOG_FILE!"
echo Generated: %date% %time% >> "!LOG_FILE!"
echo ===================================================== >> "LOG_FILE!"
echo. >> "!LOG_FILE!"

echo [1/10] Repository location
echo [1/10] Repository location >> "!LOG_FILE!"
echo SCRIPT_DIR=!SCRIPT_DIR!
echo SCRIPT_DIR=!SCRIPT_DIR! >> "LOG_FILE!"
echo. 
echo. >> "LOG_FILE!"

echo [2/10] host\.env check
echo [2/10] host\.env check >> "LOG_FILE!"
if exist "!ENV_FILE!" (
    echo [OK] !ENV_FILE! found
    echo [OK] !ENV_FILE! found >> "LOG_FILE!"
    echo ---- DATABASE_URL ----
echo ---- DATABASE_URL ---- >> "LOG_FILE!"
    findstr /b "DATABASE_URL=" "!ENV_FILE!"
    findstr /b "DATABASE_URL=" "!ENV_FILE!" >> "LOG_FILE!"
) else (
    echo [ERROR] !ENV_FILE! not found
    echo [ERROR] !ENV_FILE! not found >> "LOG_FILE!"
)
echo.
echo. >> "LOG_FILE!"

echo [3/10] PostgreSQL services
echo [3/10] PostgreSQL services >> "LOG_FILE!"
sc query state= all | findstr /i postgres
sc query state= all | findstr /i postgres >> "LOG_FILE!"
echo.
echo. >> "LOG_FILE!"

echo [4/10] Port 5432 listeners
echo [4/10] Port 5432 listeners >> "LOG_FILE!"
netstat -ano | findstr :5432
netstat -ano | findstr :5432 >> "LOG_FILE!"
echo.
echo. >> "LOG_FILE!"

echo [5/10] psql existence
echo [5/10] psql existence >> "LOG_FILE!"
where psql
where psql >> "LOG_FILE!" 2>&1
echo.
echo. >> "LOG_FILE!"

echo [6/10] Database list via postgres user
echo [6/10] Database list via postgres user >> "LOG_FILE!"
echo If prompted, enter postgres password.
echo If prompted, enter postgres password. >> "LOG_FILE!"
psql -h localhost -p 5432 -U postgres -l
psql -h localhost -p 5432 -U postgres -l >> "LOG_FILE!" 2>&1
echo.
echo. >> "LOG_FILE!"

echo [7/10] Role list via postgres user
echo [7/10] Role list via postgres user >> "LOG_FILE!"
psql -h localhost -p 5432 -U postgres -c "\du"
psql -h localhost -p 5432 -U postgres -c "\du" >> "LOG_FILE!" 2>&1
echo.
echo. >> "LOG_FILE!"

echo [8/10] Direct login test as bsapp
echo [8/10] Direct login test as bsapp >> "LOG_FILE!"
echo If prompted, enter password for user bsapp.
echo If prompted, enter password for user bsapp. >> "LOG_FILE!"
psql -h localhost -p 5432 -U bsapp -d bsapp -c "select current_database(), current_user;"
psql -h localhost -p 5432 -U bsapp -d bsapp -c "select current_database(), current_user;" >> "LOG_FILE!" 2>&1
echo.
echo. >> "LOG_FILE!"

echo [9/10] Backend startup test
echo [9/10] Backend startup test >> "LOG_FILE!"
if exist "!HOST_DIR!" (
    pushd "!HOST_DIR!"
    echo Running: uv run uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
echo Running: uv run uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload >> "LOG_FILE!"
    uv run uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
    uv run uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload >> "LOG_FILE!" 2>&1
    popd
) else (
    echo [ERROR] host directory not found
    echo [ERROR] host directory not found >> "LOG_FILE!"
)
echo.
echo. >> "LOG_FILE!"

echo [10/10] Finished
echo [10/10] Finished >> "LOG_FILE!"
echo Result log: !LOG_FILE!
echo Result log: !LOG_FILE! >> "LOG_FILE!"
echo.
echo Done.
endlocal
