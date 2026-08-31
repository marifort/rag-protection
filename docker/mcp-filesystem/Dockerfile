# Layer 2 MCP filesystem backend — pre-install server so runtime needs no npm registry
# (mcp-backends network is internal-only; npx -y would hang at container start).
FROM supercorp/supergateway:latest

RUN npm install -g @modelcontextprotocol/server-filesystem
