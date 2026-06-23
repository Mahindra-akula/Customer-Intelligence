# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

- Python 3.11.9 virtual environment at `.venv/` (created with `python -m venv .venv`)
- Activate: `.venv/Scripts/activate` (Windows) or `source .venv/bin/activate` (Unix)
- Currently only `pip` and `setuptools` are installed — add dependencies as the project takes shape

## Context

This project lives alongside **ADB-preso** (`../ADB-preso/`), a Databricks retail replenishment demo. If this project follows a similar pattern, expect:
- Databricks Asset Bundle (`databricks.yml`) for deployment
- FastAPI + React frontend served as a Databricks App
- DLT pipeline (bronze → silver → gold) in Unity Catalog
- Serverless compute only (Free Edition constraints apply)
