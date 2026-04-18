@echo off
REM Install JCAMP FxScalper ML Prediction Service as a Windows service
REM Requires NSSM (https://nssm.cc/) to be installed and on PATH
REM
REM Run this script as Administrator on the VPS

SET SERVICE_NAME=JCAMP_FxScalper_ML_API
SET PYTHON_PATH=C:\Python311\python.exe
SET APP_DIR=D:\JCAMP_FxScalper_ML\predict_service
SET LOG_DIR=D:\JCAMP_Logs

REM Create log directory
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM Install the service
nssm install %SERVICE_NAME% %PYTHON_PATH% -m uvicorn app:app --host 127.0.0.1 --port 8000
nssm set %SERVICE_NAME% AppDirectory %APP_DIR%
nssm set %SERVICE_NAME% AppStdout %LOG_DIR%\predict_service_stdout.log
nssm set %SERVICE_NAME% AppStderr %LOG_DIR%\predict_service_stderr.log
nssm set %SERVICE_NAME% AppRotateFiles 1
nssm set %SERVICE_NAME% AppRotateBytes 10485760

REM Auto-start on boot
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START

REM Restart on failure (after 5 second delay)
nssm set %SERVICE_NAME% AppExit Default Restart
nssm set %SERVICE_NAME% AppRestartDelay 5000

echo.
echo Service "%SERVICE_NAME%" installed.
echo.
echo To start:  nssm start %SERVICE_NAME%
echo To stop:   nssm stop %SERVICE_NAME%
echo To remove: nssm remove %SERVICE_NAME% confirm
echo.
echo IMPORTANT: Update PYTHON_PATH and APP_DIR above to match your VPS paths.
pause
