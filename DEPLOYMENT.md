# Voice Ledger Deployment Guide

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.9+
- Foundry (for blockchain development)
- OpenAI API key

### Installation

1. **Clone Repository**
```bash
git clone <repository-url>
cd Voice-Ledger
```

2. **Set Up Environment Variables**
```bash
cd docker
cp .env.example .env
# Edit .env with your API keys
```

3. **Start Services with Docker Compose**
```bash
docker-compose up -d
```

This starts:
- **Blockchain Node** (Anvil) on port 8545
- **Voice API** on port 8000
- **DPP Resolver** on port 8001

### Without Docker

1. **Create Virtual Environment**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install Dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure Environment**
```bash
cp .env.example .env
# Edit .env with your OpenAI API key and other settings
```

4. **Start Services**

Terminal 1 - Blockchain:
```bash
cd blockchain
anvil --port 8545
```

Terminal 2 - Voice API:
```bash
python -m uvicorn voice.service.api:app --host 0.0.0.0 --port 8000
```

Terminal 3 - DPP Resolver:
```bash
python -m uvicorn dpp.dpp_resolver:app --host 0.0.0.0 --port 8001
```

Terminal 4 - Dashboard:
```bash
streamlit run dashboard/app.py --server.port 8502
```

---

## 📚 API Documentation

### Voice API (Port 8000)

**Health Check**
```bash
curl http://localhost:8000/
```

**Submit Audio for Processing**
```bash
curl -X POST http://localhost:8000/asr-nlu \
  -H "X-API-Key: your-api-key" \
  -F "file=@audio.wav"
```

Response:
```json
{
  "transcript": "Commission 50 bags of washed coffee",
  "intent": "record_commission",
  "entities": {
    "quantity": 50,
    "unit": "bags",
    "product": "washed coffee"
  }
}
```

### DPP Resolver API (Port 8001)

**Get DPP Summary**
```bash
curl http://localhost:8001/dpp/BATCH-2025-001?format=summary
```

Response:
```json
{
  "passportId": "DPP-BATCH-2025-001",
  "product": "Ethiopian Yirgacheffe",
  "quantity": "50 bags",
  "origin": "Yirgacheffe, ET",
  "eudrCompliant": true,
  "deforestationRisk": "none"
}
```

**Verify DPP**
```bash
curl http://localhost:8001/dpp/BATCH-2025-001/verify
```

**List All Batches**
```bash
curl http://localhost:8001/batches
```

---

## 🧪 Testing

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test Suites
```bash
# Voice API tests
pytest tests/test_voice_api.py -v

# Blockchain anchoring tests
pytest tests/test_anchor_flow.py -v

# SSI credential tests
pytest tests/test_ssi.py -v

# DPP tests
pytest tests/test_dpp.py -v
```

### Integration Test
```bash
python -m tests.test_dpp_flow
```

---

## 🔧 Configuration

### Environment Variables

**Required:**
- `OPENAI_API_KEY` - Your OpenAI API key for Whisper and GPT
- `VOICE_LEDGER_API_KEY` - API key for Voice API authentication

**Optional:**
- `BLOCKCHAIN_RPC_URL` - Blockchain RPC endpoint (default: http://localhost:8545)
- `VOICE_API_URL` - Voice API URL for internal calls
- `DPP_RESOLVER_URL` - DPP Resolver URL for internal calls

### Smart Contract Deployment

1. **Start Anvil Node**
```bash
cd blockchain
anvil --port 8545
```

2. **Deploy Contracts**
```bash
forge script script/Deploy.s.sol --rpc-url http://localhost:8545 --broadcast
```

3. **Verify Deployment**
```bash
forge verify-contract <contract-address> <ContractName> --rpc-url http://localhost:8545
```

---

## 📊 Monitoring

### Dashboard Access
Open your browser to: http://localhost:8502

Features:
- **Overview** - System metrics and recent activity
- **Batches** - Detailed batch information
- **Analytics** - Volume distribution and event statistics
- **System Health** - Service status and data statistics

### Logs

**Docker Logs:**
```bash
docker-compose logs -f voice-api
docker-compose logs -f dpp-resolver
docker-compose logs -f blockchain
```

**Local Logs:**
Check application output in respective terminals

---

## 🔄 Workflow Example

### Complete Batch Traceability Flow

1. **Create Batch (via Voice)**
```bash
# Record audio saying: "Commission 50 bags of washed coffee from Guzo Cooperative"
curl -X POST http://localhost:8000/asr-nlu \
  -H "X-API-Key: your-key" \
  -F "file=@commission.wav"
```

2. **Create EPCIS Event**
```bash
python -c "from epcis.epcis_builder import create_commission_event; print(create_commission_event('BATCH-2025-001'))"
```

3. **Hash Event**
```bash
python -c "from epcis.hash_event import hash_event; from pathlib import Path; print(hash_event(Path('epcis/events/BATCH-2025-001_commission.json')))"
```

4. **Record in Digital Twin**
```bash
python -c "from twin.twin_builder import record_anchor, record_token, record_settlement; record_anchor('BATCH-2025-001', 'hash123...', 'commissioning'); record_token('BATCH-2025-001', 1, 50, {'origin': 'Ethiopia'}); record_settlement('BATCH-2025-001', 1000000, '0xRecipient')"
```

5. **Generate DPP**
```bash
python -m dpp.dpp_builder
```

6. **Generate QR Code**
```bash
python -m dpp.qrcode_gen
```

7. **View DPP**
```bash
curl http://localhost:8001/dpp/BATCH-2025-001?format=summary
```

---

## 🐳 Docker Commands

### Start Services
```bash
docker-compose up -d
```

### Stop Services
```bash
docker-compose down
```

### View Logs
```bash
docker-compose logs -f
```

### Rebuild After Code Changes
```bash
docker-compose down
docker-compose build
docker-compose up -d
```

### Clean Up Volumes
```bash
docker-compose down -v
```

---

## 🔒 Security Considerations

### Production Deployment

1. **API Keys**
   - Use strong, randomly generated API keys
   - Rotate keys regularly
   - Store in secure environment variables or secrets manager

2. **Blockchain**
   - Use production blockchain network (Ethereum, Polygon)
   - Secure private keys with hardware wallet or KMS
   - Implement proper gas management

3. **HTTPS**
   - Use SSL/TLS certificates for all APIs
   - Configure reverse proxy (nginx) for production
   - Enable CORS only for trusted domains

4. **Data Protection**
   - Encrypt sensitive data at rest
   - Use secure database for digital twin storage
   - Implement backup and recovery procedures

---

## 📈 Performance Optimization

### Caching
- Enable Redis for API response caching
- Cache DPP data for frequently accessed batches
- Use CDN for QR code images

### Database
- Use PostgreSQL for production digital twin storage
- Index batch IDs and event hashes
- Regular vacuum and analyze operations

### Scaling
- Use container orchestration (Kubernetes) for horizontal scaling
- Load balance API requests
- Separate read and write workloads

---

## 🆘 Troubleshooting

### Common Issues

**Port Already in Use**
```bash
# Find and kill process
lsof -ti:8000 | xargs kill -9
```

**Docker Build Fails**
```bash
# Clean Docker cache
docker system prune -a
docker-compose build --no-cache
```

**Tests Fail**
```bash
# Clear test artifacts
rm -rf .pytest_cache
rm -rf twin/digital_twin.json
pytest tests/ -v
```

**OpenAI API Errors**
- Verify API key is valid
- Check API quota and billing
- Ensure correct model access (whisper-1, gpt-3.5-turbo)

---

## 📞 Support

For issues or questions:
- Check BUILD_LOG.md for development history
- Review Technical_Guide.md for architecture details
- Run test suite to verify system integrity

---

**Version:** 1.0.0  
**Last Updated:** December 2025  
**License:** MIT
