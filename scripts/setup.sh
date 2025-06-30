#!/bin/sh
# Setup script for FastMCP OpenAPI Server
cp config/.env.example config/.env
cp config/openapi.example.json config/openapi.json
cp config/openapi.json config/openapi.json
npm install
