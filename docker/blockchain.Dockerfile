# Voice Ledger - Blockchain Node
FROM ghcr.io/foundry-rs/foundry:latest

WORKDIR /app

# Copy blockchain contracts and configuration
COPY blockchain/ ./blockchain/

WORKDIR /app/blockchain

# Build contracts
RUN forge build

# Expose Anvil RPC port
EXPOSE 8545

# Run local Anvil node with fixed accounts for testing
CMD ["anvil", "--host", "0.0.0.0", "--port", "8545", "--accounts", "10", "--balance", "10000"]
