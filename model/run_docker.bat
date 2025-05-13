@echo off
SETLOCAL

cd %~dp0\..

echo Building the file classifier Docker image...
docker-compose -f model/docker-compose.yml build

echo.
echo Starting the file classifier container...
echo The model training will begin automatically.
echo.

docker-compose -f model/docker-compose.yml up

echo.
echo Container has exited. You can find the trained model in model/saved_models/

PAUSE
ENDLOCAL 