@echo off
title JiraBot Web - Painel Interativo de Controle e Lancamentos
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao foi encontrado no PATH do sistema.
    echo Por favor, instale o Python ou adicione ao PATH.
    pause
    exit /b 1
)

python cli.py web

if %errorlevel% neq 0 (
    echo.
    echo Ocorreu um erro durante a execucao do Painel Web.
    pause
)
