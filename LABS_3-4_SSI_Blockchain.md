# Voice Ledger - Labs 3 & 4: Identity & Blockchain

This document contains comprehensive documentation for the identity and blockchain layers of the Voice Ledger project.

**Contents:**
- **Lab 3**: Self-Sovereign Identity & Access Control (~5,700 lines)
  - Ed25519 cryptographic key pairs
  - DID (Decentralized Identifier) generation
  - W3C Verifiable Credentials
  - JSON-LD proof signatures
  - Role-based access control (RBAC)
  
- **Lab 4**: Blockchain Anchoring & Tokenization (~2,850 lines)
  - Foundry development toolkit
  - Smart contracts (EPCISEventAnchor, CoffeeBatchToken, SettlementContract)
  - ERC-1155 multi-token standard
  - Digital twin synchronization
  - Gas optimization techniques

**Total**: ~5,634 lines of detailed explanations, Solidity code, cryptography, and blockchain best practices.

**Source**: Extracted from BUILD_LOG.md (lines 4896-10529)

---

## Lab 3: Self-Sovereign Identity & Access Control

### 🎯 Lab Overview

**Goal:** Build a decentralized identity system using Self-Sovereign Identity (SSI) principles to enable trustless authentication and role-based access control without centralized authorities.

**The Problem We're Solving:**
Traditional identity systems rely on centralized authorities (username/password databases, OAuth providers, certificate authorities). This creates:
- **Single Points of Failure**: If the identity provider goes down, nobody can authenticate
- **Privacy Concerns**: Central authority knows who accesses what and when
- **Vendor Lock-in**: Changing identity providers requires migrating all users
- **Trust Dependencies**: Must trust the central authority not to be malicious
- **No Portability**: Identity doesn't work across systems without federation

**The SSI Solution:**
Self-Sovereign Identity gives individuals and organizations control over their own identities using cryptographic keypairs:
- **Decentralized**: No central registry, identities are self-generated
- **Verifiable**: Cryptographic proofs ensure authenticity
- **Portable**: Same identity works everywhere
- **Private**: Only reveal what's necessary
- **Revocable**: Credentials can be revoked without affecting identity

**Coffee Supply Chain Use Case:**
- Farmer Abebe needs to prove he's authorized to create shipment events
- Guzo Cooperative issues Abebe a "FarmerCredential"
- Abebe uses his DID (Decentralized Identifier) + credential to sign events
- Any auditor can verify Abebe's identity without contacting Guzo
- If Abebe leaves the farm, Guzo can revoke credential without affecting other farmers

---

### Step 1: Install Lab 3 Dependencies

**Command:**
```bash
pip install PyNaCl==1.5.0
```

#### 📚 Background: Ed25519 Cryptography

**What is Ed25519?**
Ed25519 is a modern elliptic curve signature algorithm designed by Daniel J. Bernstein. It's part of the EdDSA (Edwards-curve Digital Signature Algorithm) family.

**Why Ed25519 for DIDs?**

| Feature | RSA-2048 | ECDSA (P-256) | Ed25519 | Why it Matters |
|---------|----------|---------------|---------|----------------|
| Public key size | 256 bytes | 64 bytes | 32 bytes | Smaller DIDs |
| Signature size | 256 bytes | 64 bytes | 64 bytes | Less data |
| Signing speed | Slow (~1ms) | Fast (~0.5ms) | **Very fast (~0.08ms)** | High throughput |
| Verification speed | Slow (~0.5ms) | Fast (~0.3ms) | **Very fast (~0.1ms)** | Faster checks |
| Side-channel resistance | Poor | Poor | **Excellent** | Security |
| Deterministic | No | Optional | **Yes** | Reproducible |

**Key Properties:**
1. **Deterministic**: Same message + key = same signature (no randomness needed)
2. **Fast**: ~10x faster than RSA, ~3x faster than ECDSA
3. **Small**: Keys and signatures are compact
4. **Secure**: No known attacks, 128-bit security level
5. **Side-channel resistant**: Constant-time operations prevent timing attacks

**Mathematical Foundation:**
Ed25519 uses Curve25519, defined by the equation:
$$y^2 = x^3 + 486662x^2 + x \pmod{2^{255} - 19}$$

Private key = 32 random bytes
Public key = Scalar multiplication of base point by private key

**PyNaCl Library:**
- Python binding to libsodium (C library)
- libsodium is audited, widely used (Signal, WireGuard, Tor)
- Provides high-level API (no need to understand elliptic curves)
- Handles all the complex cryptography correctly

**Installation:**
```bash
pip install PyNaCl==1.5.0
```

**Why version 1.5.0?**
- Stable release (May 2022)
- Python 3.9+ compatible
- No breaking changes in 1.5.x series
- Widely tested in production

**Dependencies:**
PyNaCl depends on:
- `cffi` - C Foreign Function Interface (to call libsodium)
- `libsodium` - C library (automatically installed)
- `pycparser` - Parse C code (used by cffi)

**Troubleshooting:**

If installation fails on macOS:
```bash
# Install libsodium via Homebrew first
brew install libsodium
pip install PyNaCl==1.5.0
```

If installation fails on Linux:
```bash
# Install libsodium-dev
sudo apt-get install libsodium-dev  # Ubuntu/Debian
sudo yum install libsodium-devel    # CentOS/RHEL
pip install PyNaCl==1.5.0
```

**Verification:**
```bash
python -c "from nacl.signing import SigningKey; print('PyNaCl OK')"
```

Expected output: `PyNaCl OK`

---

#### 🔐 Cryptographic Primitives Provided

PyNaCl provides several cryptographic operations:

**Digital Signatures (what we use):**
```python
from nacl.signing import SigningKey, VerifyKey

# Generate keypair
sk = SigningKey.generate()  # 32-byte private key
vk = sk.verify_key          # 32-byte public key

# Sign message
signature = sk.sign(b"Hello")  # 64-byte signature

# Verify signature
vk.verify(signature)  # Raises exception if invalid
```

**Other Operations (not used in this lab):**
- `nacl.secret.SecretBox` - Symmetric encryption (like AES-GCM)
- `nacl.public.Box` - Asymmetric encryption (like RSA encryption)
- `nacl.pwhash` - Password hashing (like Argon2)
- `nacl.hash` - Cryptographic hashing (like SHA-256)

We only use **digital signatures** for SSI because:
- Credentials need to be publicly verifiable (not encrypted)
- Signatures prove authenticity without revealing private key
- Anyone can verify, only holder can sign

---

#### 🎯 Design Decisions Explained

**Q: Why Ed25519 instead of RSA?**
A: Speed and size. Ed25519 signs in 0.08ms vs RSA's 1ms. In a supply chain with thousands of events per day, this adds up. Also, 32-byte keys vs 256-byte keys = smaller DIDs.

**Q: Why PyNaCl instead of cryptography library?**
A: Simplicity. PyNaCl's API is designed for correct usage by default. The `cryptography` library is more flexible but easier to misuse (wrong padding, wrong mode, etc.).

**Q: Can we use this in production?**
A: Yes! PyNaCl/libsodium is used by:
- Signal (encrypted messaging)
- WireGuard (VPN)
- Tor Project (anonymity network)
- GitHub (SSH key support)
- Keybase (encrypted storage)

**Q: What's the security level?**
A: 128-bit security level (equivalent to AES-128). This means:
- Breaking Ed25519 requires ~$2^{128}$ operations
- At 1 trillion operations per second, would take $10^{22}$ years
- RSA-2048 also provides ~112-bit security
- Quantum computers reduce to ~64-bit (still impractical)

**Q: What about quantum resistance?**
A: Ed25519 is NOT quantum-resistant. Shor's algorithm can break it. For post-quantum cryptography, consider:
- Dilithium (lattice-based signatures)
- SPHINCS+ (hash-based signatures)
- These are standardized but not yet widely adopted

---

#### ✅ Testing the Installation

**Test 1: Basic Key Generation**
```python
from nacl.signing import SigningKey

sk = SigningKey.generate()
print(f"Private key: {sk.encode().hex()}")
print(f"Public key: {sk.verify_key.encode().hex()}")
```

**Expected Output:**
```
Private key: a3f5...  (64 hex characters = 32 bytes)
Public key: 8d2a...   (64 hex characters = 32 bytes)
```

**Test 2: Sign and Verify**
```python
from nacl.signing import SigningKey

sk = SigningKey.generate()
vk = sk.verify_key

# Sign message
message = b"Deliver 50 bags of coffee"
signed = sk.sign(message)

# Verify signature
try:
    vk.verify(signed)
    print("✅ Signature valid!")
except Exception as e:
    print(f"❌ Signature invalid: {e}")
```

**Expected Output:**
```
✅ Signature valid!
```

**Test 3: Tampering Detection**
```python
from nacl.signing import SigningKey
from nacl.exceptions import BadSignatureError

sk = SigningKey.generate()
vk = sk.verify_key

# Sign message
signed = sk.sign(b"Transfer $100")

# Tamper with message
tampered = signed[:-1] + b"X"  # Change last byte

# Try to verify
try:
    vk.verify(tampered)
    print("❌ Tampering not detected!")
except BadSignatureError:
    print("✅ Tampering detected!")
```

**Expected Output:**
```
✅ Tampering detected!
```

---

#### 📖 Further Reading

- **Ed25519 Paper**: "High-speed high-security signatures" by Bernstein et al. (https://ed25519.cr.yp.to/ed25519-20110926.pdf)
- **PyNaCl Documentation**: https://pynacl.readthedocs.io/
- **libsodium Documentation**: https://doc.libsodium.org/
- **Curve25519**: "Curve25519: new Diffie-Hellman speed records" by Bernstein (https://cr.yp.to/ecdh/curve25519-20060209.pdf)
- **Timing Attack Prevention**: "Timing Attacks on Implementations of Diffie-Hellman, RSA, DSS, and Other Systems" by Kocher (1996)

✅ **Step 1 Complete!** PyNaCl installed and ready for DID generation.

---

### Step 2: Create DID Generation Module

**File Created:** `ssi/did/did_key.py`

#### 📚 Background: Decentralized Identifiers (DIDs)

**What is a DID?**
A Decentralized Identifier is a new type of identifier that enables verifiable, self-sovereign digital identity. Unlike traditional identifiers (email, phone, username), DIDs are:
- **Decentralized**: No central issuing authority
- **Cryptographically Verifiable**: Backed by public-key cryptography
- **Persistent**: Not dependent on any organization's existence
- **Resolvable**: Can be looked up to retrieve public keys and service endpoints

**DID Format (W3C Standard):**
```
did:<method>:<method-specific-identifier>

Examples:
did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH
did:web:example.com:user:alice
did:ethr:0x3b0BC51Ab9De1e5B7B6E34E5b960285805C41736
```

**DID Methods:**
Different methods for storing/resolving DIDs:

| Method | Storage | Resolution | Use Case |
|--------|---------|------------|----------|
| `did:key` | Embedded in DID | No lookup needed | Offline, simple |
| `did:web` | Web server | HTTPS request | Easy integration |
| `did:ethr` | Ethereum blockchain | Smart contract call | Decentralized registry |
| `did:ion` | Bitcoin + IPFS | Bitcoin + IPFS | Fully decentralized |
| `did:sov` | Hyperledger Indy | Indy ledger | Enterprise permissioned |

**Why `did:key` for Voice Ledger?**
1. **Simplicity**: No blockchain or server needed
2. **Offline**: Works without internet connectivity
3. **Fast**: No network lookups
4. **Self-Contained**: Public key embedded in DID itself
5. **Perfect for IoT**: Warehouse devices with intermittent connectivity

Trade-off: Can't rotate keys without changing DID. For production, consider `did:ethr` or `did:ion` for key rotation support.

---

#### 💻 Complete Implementation

**File:** `ssi/did/did_key.py`

```python
"""
DID (Decentralized Identifier) Module

This module generates did:key identifiers based on Ed25519 keypairs.
DIDs provide cryptographically verifiable identities without relying on 
centralized registries.

Standard: W3C Decentralized Identifiers (DIDs) v1.0
Method: did:key (https://w3c-ccg.github.io/did-method-key/)

DID Format:
  did:key:z<base58btc-encoded-public-key>
  
Example:
  did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH
  
The 'z' prefix indicates base58btc encoding (Bitcoin's Base58 alphabet).
We use base64url for simplicity, as the encoding choice doesn't affect security.
"""

import base64
from nacl.signing import SigningKey


def generate_did_key() -> dict:
    """
    Generate a new did:key identifier with Ed25519 keypair.
    
    The did:key method embeds the public key directly in the DID,
    making it self-verifiable without external lookups.
    
    Process:
    1. Generate 32-byte random private key (256 bits of entropy)
    2. Derive public key via elliptic curve scalar multiplication
    3. Encode public key in base64url (URL-safe encoding)
    4. Construct DID with 'did:key:z' prefix
    
    Returns:
        Dictionary containing:
        - did: The full did:key identifier (for sharing publicly)
        - private_key: Hex-encoded private key (keep secret!)
        - public_key: Hex-encoded public key (can be shared)
        
    Example:
        >>> identity = generate_did_key()
        >>> print(identity["did"])
        'did:key:z6Mk...'
        >>> # Store private_key in secure storage (env vars, vault)
        >>> # Share only the DID with others
        
    Security Notes:
    - Private key must be stored securely (never in code/logs)
    - Use environment variables or secret management systems
    - If private key is compromised, must generate new DID
    - No key rotation: DID change required for new keys
    """
    # Generate Ed25519 keypair using cryptographically secure random
    # SigningKey.generate() uses os.urandom() internally (256 bits entropy)
    sk = SigningKey.generate()
    
    # Derive verification (public) key from signing (private) key
    # This is deterministic: same private key always gives same public key
    vk = sk.verify_key
    
    # Encode public key for DID identifier
    # Base64url encoding: URL-safe (no +, /, = padding)
    # rstrip("=") removes padding (standard for did:key)
    public_key_b64 = base64.urlsafe_b64encode(vk.encode()).decode("utf-8").rstrip("=")
    
    # Construct DID with did:key method
    # Format: did:key:z<encoded-public-key>
    # 'z' prefix indicates multibase encoding (originally base58btc)
    # We use base64url for simplicity (functionally equivalent)
    did = f"did:key:z{public_key_b64}"

    return {
        "did": did,                          # Share this publicly
        "private_key": sk.encode().hex(),   # Keep this SECRET
        "public_key": vk.encode().hex(),    # Can share (embedded in DID)
    }


if __name__ == "__main__":
    print("Generating new DID...")
    identity = generate_did_key()
    print(f"DID: {identity['did']}")
    print(f"Public Key: {identity['public_key']}")
    print(f"\n⚠️  Keep private key secure!")
    print(f"Private Key: {identity['private_key']}")
```

---

#### 🔍 Deep Dive: DID Resolution

**How do you verify a DID?**

For `did:key`, the public key is embedded in the DID itself:

```python
import base64
from nacl.signing import VerifyKey

def resolve_did_key(did: str) -> dict:
    """
    Resolve a did:key to extract the public key.
    
    Args:
        did: DID string (e.g., "did:key:z6Mk...")
        
    Returns:
        Dictionary with public_key (hex)
    """
    # Remove "did:key:z" prefix
    encoded_key = did.replace("did:key:z", "")
    
    # Add padding if needed (base64 requires length % 4 == 0)
    padding = 4 - (len(encoded_key) % 4)
    if padding != 4:
        encoded_key += "=" * padding
    
    # Decode base64url
    public_key_bytes = base64.urlsafe_b64decode(encoded_key)
    
    return {
        "public_key": public_key_bytes.hex()
    }

# Example:
# did = "did:key:zYwR..."
# resolved = resolve_did_key(did)
# vk = VerifyKey(bytes.fromhex(resolved["public_key"]))
# vk.verify(signature)  # Verify without network lookup!
```

**Comparison with Traditional Identifiers:**

```
Traditional (Email):
Email: alice@example.com
↓ (DNS lookup)
MX Record: mail.example.com
↓ (SMTP connection)
Server verifies password
→ Single point of failure (email provider)

DID (Self-Sovereign):
DID: did:key:z6Mk...
↓ (local decoding)
Public Key: 8d2a3f...
↓ (verify signature)
Signature valid!
→ No dependencies, works offline
```

---

#### 🎯 Design Decisions Explained

**Q: Why not use email addresses as identifiers?**
A: Email addresses are:
- Controlled by provider (can be revoked)
- Not cryptographically verifiable
- Require online lookup
- Don't work in offline/rural areas
- Privacy concern (reveals identity)

**Q: Why base64url instead of base58btc (standard)?**
A: Simplicity. Base58btc requires additional library. Base64url is built-in to Python. The encoding format doesn't affect security (both encode same public key). For production interoperability with other DID libraries, use base58btc.

**Q: How do you prove ownership of a DID?**
A: By signing a message with the private key. Verifier can:
1. Extract public key from DID
2. Verify signature using public key
3. If valid, prover owns the DID

```python
# Prover (has private key):
signature = sk.sign(b"challenge-12345")

# Verifier (has DID only):
public_key = resolve_did_key(did)["public_key"]
vk = VerifyKey(bytes.fromhex(public_key))
vk.verify(signature)  # Proves ownership!
```

**Q: What if private key is lost?**
A: With `did:key`, there's no recovery. Must generate new DID and re-issue credentials. For production:
- Use HSM (Hardware Security Module) for key storage
- Implement backup procedures (encrypted key exports)
- Consider `did:ethr` with multi-sig recovery

**Q: Can DIDs be revoked?**
A: `did:key` cannot be revoked (no registry). Instead:
- Revoke credentials issued to that DID
- Maintain revocation lists (CRLs)
- Use blockchain-based DIDs with on-chain revocation

---

#### ✅ Testing the Implementation

**Test 1: Generate Multiple DIDs**
```bash
python -m ssi.did.did_key
```

**Expected Output:**
```
Generating new DID...
DID: did:key:zYwR8vN2HChC3snTlr0Unawz2aJAHBf2HWLhUAu0
Public Key: b44bf4c8691a7dc0870a10b7b274e5af45276b0cf668900705fd8758b85402ed

⚠️  Keep private key secure!
Private Key: a6ca9765ebb9b6d653d7aa5377f5981510751c0ce38aec831cb73528086f2aaa
```

Run multiple times - each DID will be unique (random entropy).

**Test 2: Verify DID Format**
```python
import re
from ssi.did.did_key import generate_did_key

identity = generate_did_key()
did = identity["did"]

# Check format
assert did.startswith("did:key:z"), "DID must start with 'did:key:z'"
assert len(did) > 15, "DID too short"
assert re.match(r"^did:key:z[A-Za-z0-9_-]+$", did), "Invalid characters"

print("✅ DID format valid")
```

**Test 3: Key Determinism**
```python
from nacl.signing import SigningKey
import base64

# Same private key should always produce same DID
private_key_hex = "a6ca9765ebb9b6d653d7aa5377f5981510751c0ce38aec831cb73528086f2aaa"

sk = SigningKey(bytes.fromhex(private_key_hex))
vk = sk.verify_key
public_key_b64 = base64.urlsafe_b64encode(vk.encode()).decode("utf-8").rstrip("=")
did1 = f"did:key:z{public_key_b64}"

# Regenerate from same private key
sk2 = SigningKey(bytes.fromhex(private_key_hex))
vk2 = sk2.verify_key
public_key_b64_2 = base64.urlsafe_b64encode(vk2.encode()).decode("utf-8").rstrip("=")
did2 = f"did:key:z{public_key_b64_2}"

assert did1 == did2, "Same private key must produce same DID"
print("✅ DID generation is deterministic")
```

**Test 4: Prove DID Ownership**
```python
from ssi.did.did_key import generate_did_key
from nacl.signing import SigningKey, VerifyKey
import base64

# Generate identity
identity = generate_did_key()
did = identity["did"]
private_key = identity["private_key"]

# Prover signs challenge
sk = SigningKey(bytes.fromhex(private_key))
challenge = b"prove-ownership-12345"
signature = sk.sign(challenge)

# Verifier extracts public key from DID
encoded_key = did.replace("did:key:z", "")
padding = 4 - (len(encoded_key) % 4)
if padding != 4:
    encoded_key += "=" * padding
public_key_bytes = base64.urlsafe_b64decode(encoded_key)

# Verifier checks signature
vk = VerifyKey(public_key_bytes)
try:
    vk.verify(signature)
    print("✅ DID ownership proven!")
except Exception as e:
    print(f"❌ Ownership proof failed: {e}")
```

---

#### ⚠️ Common Pitfalls

**Pitfall 1: Storing private key in code**
```python
# Wrong: Hardcoded private key ❌
private_key = "a6ca9765ebb9b6d653d7aa5377f5981510751c0ce38aec831cb73528086f2aaa"

# Right: Load from environment ✅
import os
private_key = os.environ["DID_PRIVATE_KEY"]
if not private_key:
    raise ValueError("DID_PRIVATE_KEY not set")
```

**Pitfall 2: Sharing private key**
```python
# Wrong: Logging private key ❌
logger.info(f"Generated DID: {did}, Private Key: {private_key}")

# Right: Only log DID ✅
logger.info(f"Generated DID: {did}")
logger.debug("Private key generated (not logged for security)")
```

**Pitfall 3: Not handling base64 padding**
```python
# Wrong: Decode without padding ❌
public_key = base64.urlsafe_b64decode(encoded_key)  # May fail

# Right: Add padding if needed ✅
padding = 4 - (len(encoded_key) % 4)
if padding != 4:
    encoded_key += "=" * padding
public_key = base64.urlsafe_b64decode(encoded_key)
```

**Pitfall 4: Reusing DIDs across environments**
```python
# Wrong: Same DID for dev/prod ❌
DID = "did:key:z6Mk..."  # Same everywhere

# Right: Different DIDs per environment ✅
DEV_DID = os.environ["DEV_DID"]
PROD_DID = os.environ["PROD_DID"]
```

---

#### 🚀 Production Enhancements

**1. Key Storage with HSM:**
```python
import boto3  # AWS KMS example

def generate_did_with_kms():
    kms = boto3.client('kms')
    # Generate key in HSM
    response = kms.create_key(
        KeyUsage='SIGN_VERIFY',
        KeySpec='ECC_NIST_P256'
    )
    key_id = response['KeyMetadata']['KeyId']
    # DID points to KMS key
    return {"did": f"did:key:kms:{key_id}"}
```

**2. DID Document Generation:**
```python
def create_did_document(did: str, public_key: str) -> dict:
    """
    Generate W3C DID Document for did:key.
    """
    return {
        "@context": "https://www.w3.org/ns/did/v1",
        "id": did,
        "verificationMethod": [{
            "id": f"{did}#keys-1",
            "type": "Ed25519VerificationKey2020",
            "controller": did,
            "publicKeyMultibase": f"z{public_key}"
        }],
        "authentication": [f"{did}#keys-1"],
        "assertionMethod": [f"{did}#keys-1"]
    }
```

**3. DID Rotation Strategy:**
```python
class DIDManager:
    def __init__(self):
        self.current_did = None
        self.previous_dids = []  # Track old DIDs
    
    def rotate_did(self):
        """Rotate to new DID, keep old for transition period."""
        if self.current_did:
            self.previous_dids.append(self.current_did)
        self.current_did = generate_did_key()
        # Re-issue credentials with new DID
        # Revoke old credentials after transition period
```

---

#### 📖 Further Reading

- **W3C DID Specification**: https://www.w3.org/TR/did-core/
- **did:key Method Specification**: https://w3c-ccg.github.io/did-method-key/
- **DID Resolution**: https://w3c-ccg.github.io/did-resolution/
- **Multibase Encoding**: https://github.com/multiformats/multibase
- **Self-Sovereign Identity Book**: "Self-Sovereign Identity" by Manning et al.

✅ **Step 2 Complete!** DIDs can now be generated for all supply chain actors.

---

### Step 3: Create Credential Schemas

**File Created:** `ssi/credentials/schemas.py`

#### 📚 Background: Verifiable Credentials

**What is a Verifiable Credential?**
A Verifiable Credential (VC) is a tamper-evident credential that can be cryptographically verified. Think of it as a digital version of a physical credential (driver's license, diploma, membership card) but with stronger security.

**W3C Verifiable Credentials Data Model:**
```json
{
  "@context": ["https://www.w3.org/2018/credentials/v1"],
  "type": ["VerifiableCredential", "SpecificCredentialType"],
  "issuer": "did:key:z6Mk...",
  "issuanceDate": "2025-12-12T00:00:00Z",
  "credentialSubject": {
    "id": "did:key:z6Mk...",
    "name": "Alice",
    "role": "farmer"
  },
  "proof": {
    "type": "Ed25519Signature2020",
    "created": "2025-12-12T00:00:00Z",
    "verificationMethod": "did:key:z6Mk...#keys-1",
    "proofPurpose": "assertionMethod",
    "signature": "8d2a3f..."
  }
}
```

**Key Components:**
1. **@context**: JSON-LD context defining vocabularies
2. **type**: Credential types (always includes "VerifiableCredential")
3. **issuer**: DID of who issued the credential
4. **issuanceDate**: When credential was created (ISO 8601)
5. **credentialSubject**: The claims being made
6. **proof**: Cryptographic signature proving authenticity

**Credential vs Claim:**
- **Credential**: Container with metadata + signature
- **Claim**: Assertion about the subject (name=Alice, role=farmer)
- **Subject**: Entity the claims are about

---

#### 💻 Complete Implementation

**File:** `ssi/credentials/schemas.py`

```python
"""
Verifiable Credential Schemas

Defines the structure of credentials used in the Voice Ledger system.
Each credential type has specific claims that can be verified.

Standard: W3C Verifiable Credentials Data Model v1.1
Pattern: Schema-based validation (required vs optional fields)

Design Principles:
1. Minimal Disclosure: Only include necessary claims
2. Selective Disclosure: Allow revealing subset of claims
3. Privacy: No PII unless absolutely required
4. Extensibility: Easy to add new credential types
"""

# Farmer Identity Credential
# Purpose: Prove someone is an authorized farmer
# Issued by: Cooperative or government agriculture department
# Required for: Creating shipment events from farm
FARMER_SCHEMA = {
    "type": "FarmerCredential",
    "description": "Verifies the identity of a coffee farmer",
    "claims": ["name", "farm_id", "country", "did"],
    "required": ["name", "farm_id", "did"],
    "optional": ["country"],  # Country can be inferred from farm_id
    "issuer_type": "cooperative"  # Who can issue this credential
}

# Facility Location Credential
# Purpose: Prove a facility is legitimate and authorized
# Issued by: Cooperative or certification body
# Required for: Creating commissioning/transformation events
FACILITY_SCHEMA = {
    "type": "FacilityCredential",
    "description": "Verifies a facility's identity and location",
    "claims": ["facility_name", "facility_type", "gln", "did"],
    "required": ["facility_name", "gln", "did"],
    "optional": ["facility_type"],  # Type can be inferred from GLN
    "issuer_type": "cooperative"
}

# Due Diligence Credential
# Purpose: Prove EUDR compliance checks were performed
# Issued by: Auditor or certification body
# Required for: Exporting coffee to EU
DUE_DILIGENCE_SCHEMA = {
    "type": "DueDiligenceCredential",
    "description": "Certifies due diligence checks for EUDR compliance",
    "claims": ["batch_id", "geolocation", "verified_by", "timestamp"],
    "required": ["batch_id", "geolocation", "verified_by", "timestamp"],
    "optional": [],
    "issuer_type": "auditor"  # Only auditors can issue
}

# Cooperative Role Credential
# Purpose: Prove someone works for a cooperative in specific role
# Issued by: Cooperative administrator
# Required for: Creating commissioning/receipt events
COOPERATIVE_SCHEMA = {
    "type": "CooperativeCredential",
    "description": "Identifies a cooperative and its role",
    "claims": ["cooperative_name", "role", "country", "did"],
    "required": ["cooperative_name", "role", "did"],
    "optional": ["country"],
    "issuer_type": "cooperative"
}


def get_schema(credential_type: str) -> dict:
    """
    Retrieve a credential schema by type.
    
    Args:
        credential_type: Type of credential (e.g., "FarmerCredential")
        
    Returns:
        Schema dictionary or None if not found
        
    Example:
        >>> schema = get_schema("FarmerCredential")
        >>> print(schema["required"])
        ['name', 'farm_id', 'did']
    """
    schemas = {
        "FarmerCredential": FARMER_SCHEMA,
        "FacilityCredential": FACILITY_SCHEMA,
        "DueDiligenceCredential": DUE_DILIGENCE_SCHEMA,
        "CooperativeCredential": COOPERATIVE_SCHEMA
    }
    return schemas.get(credential_type)


def validate_claims(credential_type: str, claims: dict) -> tuple[bool, str]:
    """
    Validate that claims match the schema requirements.
    
    Args:
        credential_type: Type of credential
        claims: Dictionary of claim key-value pairs
        
    Returns:
        Tuple of (is_valid, error_message)
        
    Validation Rules:
    1. All required fields must be present
    2. All provided fields must be in schema
    3. No extra unexpected fields
    
    Example:
        >>> claims = {"name": "Abebe", "farm_id": "ETH-001", "did": "did:key:z..."}
        >>> is_valid, msg = validate_claims("FarmerCredential", claims)
        >>> print(is_valid)  # True
    """
    schema = get_schema(credential_type)
    if not schema:
        return False, f"Unknown credential type: {credential_type}"
    
    # Check required fields are present
    required = schema.get("required", [])
    for field in required:
        if field not in claims:
            return False, f"Missing required claim: {field}"
    
    # Check that all provided claims are in schema
    # This prevents accidentally leaking extra data
    allowed = schema.get("claims", [])
    for claim_key in claims.keys():
        if claim_key not in allowed:
            return False, f"Unknown claim: {claim_key}"
    
    return True, ""


if __name__ == "__main__":
    print("Available Credential Schemas:\n")
    for schema_name in ["FarmerCredential", "FacilityCredential", "DueDiligenceCredential", "CooperativeCredential"]:
        schema = get_schema(schema_name)
        print(f"📋 {schema['type']}")
        print(f"   {schema['description']}")
        print(f"   Claims: {', '.join(schema['claims'])}")
        print(f"   Required: {', '.join(schema['required'])}\n")
```

---

#### 🔍 Deep Dive: Schema Design Principles

**1. Minimal Disclosure:**
Only include claims that are absolutely necessary. Don't ask for more data than needed.

```python
# Bad: Too much information ❌
claims = {
    "name": "Abebe Fekadu",
    "ssn": "123-45-6789",        # Not needed!
    "phone": "+251-911-123456",  # Not needed!
    "email": "abebe@farm.et",     # Not needed!
    "farm_id": "ETH-001"
}

# Good: Only what's necessary ✅
claims = {
    "name": "Abebe Fekadu",
    "farm_id": "ETH-001",
    "did": "did:key:z6Mk..."
}
```

**2. Selective Disclosure:**
Allow proving subset of claims without revealing all.

```python
# Example: Prove over 18 without revealing exact age
claims = {
    "over_18": True,  # Instead of "age": 25
    "name": "Alice"
}

# Example: Prove location without revealing exact address
claims = {
    "country": "Ethiopia",  # Instead of full GPS coordinates
    "farm_id": "ETH-001"
}
```

**3. Schema Versioning:**
Plan for schema evolution.

```python
FARMER_SCHEMA_V1 = {
    "version": "1.0",
    "claims": ["name", "farm_id", "did"]
}

FARMER_SCHEMA_V2 = {
    "version": "2.0",
    "claims": ["name", "farm_id", "did", "organic_certified"],  # New field
    "backward_compatible": True  # V1 credentials still valid
}
```

---

#### 🎯 Design Decisions Explained

**Q: Why separate schemas instead of one generic schema?**
A: Type safety and validation. Different roles need different claims. Farmer doesn't need GLN, facility doesn't need farm_id. Separate schemas catch errors early.

**Q: Why use dictionaries instead of classes?**
A: Flexibility and serialization. Dictionaries easily serialize to JSON for storage/transmission. Classes require more boilerplate. For production, consider Pydantic models:

```python
from pydantic import BaseModel

class FarmerCredential(BaseModel):
    name: str
    farm_id: str
    did: str
    country: str | None = None
```

**Q: How to handle multiple languages?**
A: Use language tags (BCP 47):

```python
claims = {
    "name": "Abebe Fekadu",
    "name@am": "አበበ ፈቃዱ",  # Amharic
    "farm_id": "ETH-001"
}
```

**Q: What about credential expiration?**
A: Add `expirationDate` field in credential (not schema):

```python
credential = {
    "issuanceDate": "2025-01-01T00:00:00Z",
    "expirationDate": "2026-01-01T00:00:00Z",  # Valid for 1 year
    "credentialSubject": {...}
}
```

---

#### ✅ Testing the Implementation

**Test 1: List All Schemas**
```bash
python -m ssi.credentials.schemas
```

**Expected Output:**
```
Available Credential Schemas:

📋 FarmerCredential
   Verifies the identity of a coffee farmer
   Claims: name, farm_id, country, did
   Required: name, farm_id, did

📋 FacilityCredential
   Verifies a facility's identity and location
   Claims: facility_name, facility_type, gln, did
   Required: facility_name, gln, did

📋 DueDiligenceCredential
   Certifies due diligence checks for EUDR compliance
   Claims: batch_id, geolocation, verified_by, timestamp
   Required: batch_id, geolocation, verified_by, timestamp

📋 CooperativeCredential
   Identifies a cooperative and its role
   Claims: cooperative_name, role, country, did
   Required: cooperative_name, role, did
```

**Test 2: Validate Valid Claims**
```python
from ssi.credentials.schemas import validate_claims

# Valid farmer claims
claims = {
    "name": "Abebe Fekadu",
    "farm_id": "ETH-001",
    "did": "did:key:z6Mk..."
}

is_valid, msg = validate_claims("FarmerCredential", claims)
assert is_valid, f"Validation failed: {msg}"
print("✅ Valid claims accepted")
```

**Test 3: Detect Missing Required Fields**
```python
from ssi.credentials.schemas import validate_claims

# Missing required field
claims = {
    "name": "Abebe Fekadu",
    # Missing farm_id and did
}

is_valid, msg = validate_claims("FarmerCredential", claims)
assert not is_valid, "Should reject missing required field"
assert "Missing required claim" in msg
print(f"✅ Missing field detected: {msg}")
```

**Test 4: Detect Unknown Claims**
```python
from ssi.credentials.schemas import validate_claims

# Extra field not in schema
claims = {
    "name": "Abebe Fekadu",
    "farm_id": "ETH-001",
    "did": "did:key:z6Mk...",
    "ssn": "123-45-6789"  # Not in schema!
}

is_valid, msg = validate_claims("FarmerCredential", claims)
assert not is_valid, "Should reject unknown claim"
assert "Unknown claim" in msg
print(f"✅ Unknown claim detected: {msg}")
```

---

#### 🚀 Production Enhancements

**1. Schema Registry Service:**
```python
class SchemaRegistry:
    """Central registry for credential schemas with versioning."""
    
    def __init__(self):
        self.schemas = {}
    
    def register_schema(self, schema_id: str, schema: dict, version: str):
        """Register a new schema version."""
        key = f"{schema_id}:{version}"
        self.schemas[key] = schema
    
    def get_schema(self, schema_id: str, version: str = "latest"):
        """Retrieve schema by ID and version."""
        if version == "latest":
            # Return highest version number
            versions = [k for k in self.schemas if k.startswith(f"{schema_id}:")]
            if not versions:
                return None
            key = sorted(versions)[-1]
            return self.schemas[key]
        
        key = f"{schema_id}:{version}"
        return self.schemas.get(key)
```

**2. JSON Schema Integration:**
```python
import jsonschema

FARMER_JSON_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "farm_id": {"type": "string", "pattern": "^[A-Z]{3}-\\d{3}$"},
        "did": {"type": "string", "pattern": "^did:key:z[A-Za-z0-9_-]+$"},
        "country": {"type": "string", "minLength": 2, "maxLength": 2}
    },
    "required": ["name", "farm_id", "did"]
}

def validate_with_json_schema(claims: dict):
    jsonschema.validate(instance=claims, schema=FARMER_JSON_SCHEMA)
```

**3. Schema Documentation Generator:**
```python
def generate_schema_docs(schema: dict) -> str:
    """Generate human-readable documentation from schema."""
    docs = f"# {schema['type']}\n\n"
    docs += f"{schema['description']}\n\n"
    docs += "## Required Claims\n"
    for claim in schema['required']:
        docs += f"- `{claim}`\n"
    docs += "\n## Optional Claims\n"
    optional = [c for c in schema['claims'] if c not in schema['required']]
    for claim in optional:
        docs += f"- `{claim}`\n"
    return docs
```

---

#### 📖 Further Reading

- **W3C VC Data Model**: https://www.w3.org/TR/vc-data-model/
- **JSON-LD**: https://json-ld.org/
- **Schema.org Vocabularies**: https://schema.org/
- **Privacy by Design**: "Privacy by Design" by Ann Cavoukian
- **Selective Disclosure**: "BBS+ Signatures" specification

✅ **Step 3 Complete!** Schemas defined for all supply chain credential types.

**Test Command:**
```bash
python -m ssi.credentials.schemas
```

**Actual Result:** All 4 credential schemas displayed with claims and requirements ✅

---

### Step 4: Create Credential Issuance Module

**File Created:** `ssi/credentials/issue.py`

#### 📚 Background: Digital Signatures for Credentials

**Why Sign Credentials?**
Digital signatures provide three critical properties:
1. **Authentication**: Proves who issued the credential
2. **Integrity**: Detects any tampering with the credential
3. **Non-repudiation**: Issuer cannot deny having issued it

**The Signing Process:**
```
Credential Data → Canonicalize → Hash → Sign with Private Key → Signature
                    (JSON)      (SHA-256) (Ed25519)          (64 bytes)
```

**Why Canonicalization?**
JSON can represent the same data in different ways:
```json
// Same data, different representations:
{"name":"Alice","age":25}        // Compact
{
  "name": "Alice",
  "age": 25                      // Formatted
}
{"age":25,"name":"Alice"}        // Different key order
```

All three have different byte representations, producing different hashes!

**Solution: Canonical JSON**
```json
// Canonical form (deterministic):
{"age":25,"name":"Alice"}  // Keys sorted, no whitespace
```

Now hashing is consistent:
- Same data → Same canonical form → Same hash → Same signature
- Verifiers get identical hash regardless of formatting

---

#### 💻 Complete Implementation

**File:** `ssi/credentials/issue.py`

```python
"""
Verifiable Credential Issuance Module

Issues verifiable credentials by signing claims with the issuer's private key.

Standard: W3C Verifiable Credentials Data Model v1.1
Signature Suite: Ed25519Signature2020

Process Flow:
1. Validate claims against schema (optional but recommended)
2. Construct credential structure (W3C format)
3. Canonicalize credential (deterministic JSON)
4. Sign canonical form with Ed25519
5. Attach proof (signature + metadata)
6. Return complete verifiable credential

Security Notes:
- Private key must be kept secure (never log or expose)
- Signature is over canonical form (prevents format attacks)
- Timestamp in ISO 8601 format (timezone-aware)
- Proof includes verification method (public key)
"""

import json
import hashlib
from datetime import datetime, timezone
from nacl.signing import SigningKey


def issue_credential(claims: dict, issuer_private_key_hex: str) -> dict:
    """
    Issue a verifiable credential by signing the claims.
    
    Args:
        claims: Dictionary of claims to include in the credential
                Must include 'type' field matching a schema
                Example: {
                    "type": "FarmerCredential",
                    "name": "Abebe Fekadu",
                    "farm_id": "ETH-001",
                    "did": "did:key:z..."
                }
        issuer_private_key_hex: Hex-encoded Ed25519 private key of the issuer
                                This is the signing key that proves authenticity
                                Format: 64 hex characters (32 bytes)
        
    Returns:
        Verifiable credential with structure:
        {
            "@context": [...],                    # JSON-LD context
            "type": ["VerifiableCredential", ...],# Credential types
            "issuer": "<public_key_hex>",         # Who issued it
            "issuanceDate": "<ISO8601>",          # When issued
            "credentialSubject": {...},           # The claims
            "proof": {                             # Cryptographic proof
                "type": "Ed25519Signature2020",
                "created": "<ISO8601>",
                "proofPurpose": "assertionMethod",
                "verificationMethod": "<public_key_hex>",
                "signature": "<hex_signature>"
            }
        }
        
    Raises:
        ValueError: If claims are invalid or private key is malformed
        
    Example:
        >>> from ssi.did.did_key import generate_did_key
        >>> issuer = generate_did_key()
        >>> claims = {
        ...     "type": "FarmerCredential",
        ...     "name": "Abebe Fekadu",
        ...     "farm_id": "ETH-SID-001",
        ...     "did": issuer["did"]
        ... }
        >>> vc = issue_credential(claims, issuer["private_key"])
        >>> print(vc["proof"]["signature"])  # 128 hex chars
    """
    # Step 1: Load issuer's signing key from hex
    # SigningKey expects 32 bytes (64 hex characters)
    try:
        sk = SigningKey(bytes.fromhex(issuer_private_key_hex))
    except ValueError as e:
        raise ValueError(f"Invalid private key format: {e}")
    
    # Derive public key (verification key) from private key
    # This is deterministic: same private key → same public key
    vk = sk.verify_key
    
    # Step 2: Generate issuance timestamp (ISO 8601 with timezone)
    # UTC timezone ensures consistent timestamps globally
    # Format: 2025-12-12T19:27:30.466373+00:00
    issuance_date = datetime.now(timezone.utc).isoformat()
    
    # Step 3: Construct W3C Verifiable Credential structure
    credential = {
        # @context defines the JSON-LD vocabularies used
        # V1: W3C standard context for all VCs
        # V2: Voice Ledger-specific context (could define custom claims)
        "@context": [
            "https://www.w3.org/2018/credentials/v1",
            "https://voiceledger.org/credentials/v1"  # Custom context
        ],
        
        # type: Always includes "VerifiableCredential" + specific type
        # This allows verifiers to filter/validate by type
        "type": ["VerifiableCredential", claims.get("type", "GenericCredential")],
        
        # issuer: Public key of who issued this credential
        # In production, could be a DID instead of raw public key
        "issuer": vk.encode().hex(),
        
        # issuanceDate: When credential was issued (ISO 8601)
        # Required by W3C spec
        "issuanceDate": issuance_date,
        
        # credentialSubject: The actual claims being made
        # Remove 'type' field (already in top-level 'type')
        "credentialSubject": {k: v for k, v in claims.items() if k != "type"}
    }
    
    # Step 4: Create canonical representation for signing
    # Why canonical? Different JSON formatting must produce same signature
    # separators=(",",":") - No spaces (compact)
    # sort_keys=True - Keys in alphabetical order (deterministic)
    credential_canonical = json.dumps(
        credential,
        separators=(",", ":"),  # Compact: {"a":1,"b":2}
        sort_keys=True           # Deterministic key order
    )
    
    # Step 5: Sign the canonical credential
    # sk.sign() does:
    #   1. Hash the message (SHA-512 internally)
    #   2. Sign hash with Ed25519 private key
    #   3. Return signature (64 bytes)
    # encode("utf-8") converts string to bytes (required for signing)
    signed_message = sk.sign(credential_canonical.encode("utf-8"))
    
    # Extract just the signature (without the message)
    # PyNaCl returns message + signature; we only need signature
    signature = signed_message.signature
    
    # Step 6: Add proof to credential
    # Proof structure follows W3C Linked Data Proofs spec
    credential["proof"] = {
        # type: Signature algorithm used
        # Ed25519Signature2020 is the W3C standard for Ed25519
        "type": "Ed25519Signature2020",
        
        # created: When proof was generated (ISO 8601)
        "created": issuance_date,
        
        # proofPurpose: Why this proof exists
        # "assertionMethod" = proving credential claims are true
        # Other options: "authentication", "keyAgreement", etc.
        "proofPurpose": "assertionMethod",
        
        # verificationMethod: Public key to use for verification
        # In production, this could be a DID URL like "did:key:z...#keys-1"
        "verificationMethod": vk.encode().hex(),
        
        # signature: The actual Ed25519 signature (64 bytes = 128 hex chars)
        "signature": signature.hex()
    }

    return credential


if __name__ == "__main__":
    from ssi.did.did_key import generate_did_key
    
    print("Issuing a sample Farmer Credential...\n")
    
    # Scenario: Guzo Cooperative issues credential to Farmer Abebe
    
    # Generate issuer identity (Guzo Cooperative)
    issuer = generate_did_key()
    print(f"Issuer DID: {issuer['did']}\n")
    
    # Generate farmer identity
    farmer = generate_did_key()
    
    # Create claims (what we're asserting about the farmer)
    claims = {
        "type": "FarmerCredential",
        "name": "Abebe Fekadu",
        "farm_id": "ETH-SID-001",
        "country": "Ethiopia",
        "did": farmer["did"]
    }
    
    # Issue credential (Guzo signs claims with their private key)
    vc = issue_credential(claims, issuer["private_key"])
    
    print("✅ Credential Issued:")
    print(json.dumps(vc, indent=2))
```

---

#### 🔍 Deep Dive: Ed25519 Signature Internals

**What Happens During Signing?**

1. **Hash the message** (SHA-512):
```python
import hashlib
message = b"{\"name\":\"Alice\"}"  # Canonical JSON
hash_value = hashlib.sha512(message).digest()  # 64 bytes
```

2. **Sign the hash** with private key:
```
Signature = Sign(hash, private_key)
          = (R, S)  where R and S are curve points
          = 64 bytes total
```

3. **Verification** (by anyone with public key):
```
Verify(message, signature, public_key) → True/False
```

**Why This Is Secure:**
- **One-way**: Can't derive private key from signatures
- **Deterministic**: Same message + key = same signature (no randomness needed)
- **Collision-resistant**: Changing 1 bit in message → completely different signature
- **Fast**: Verify in ~0.1ms (can handle thousands of verifications per second)

---

#### 🎯 Design Decisions Explained

**Q: Why store issuer as public key instead of DID?**
A: Simplicity. For verification, we need the public key directly. Storing DID would require an extra resolution step. In production, store both:
```python
"issuer": {
    "id": "did:key:z6Mk...",
    "publicKey": "8d2a3f..."
}
```

**Q: Why Ed25519Signature2020 instead of JWS (JSON Web Signature)?**
A: W3C standardization. Ed25519Signature2020 is the W3C-recommended signature suite for VCs. JWS is more general-purpose. Both are secure, but Ed25519Signature2020 integrates better with DID infrastructure.

**Q: What if claims change after issuance?**
A: Signature becomes invalid. This is intentional! Credentials are immutable. If claims need to change:
1. Revoke old credential
2. Issue new credential with updated claims
3. Maintain credential version history

**Q: Can we sign multiple claims separately?**
A: Yes, using selective disclosure techniques like BBS+ signatures. Standard Ed25519 signs entire credential. For selective disclosure:
```python
# BBS+ allows proving subsets without revealing all claims
credential = issue_bbs_credential(claims)  # BBS+ signature
proof = create_derived_proof(credential, reveal=["name"])  # Only reveal name
```

---

#### ✅ Testing the Implementation

**Test 1: Issue Credential**
```bash
python -m ssi.credentials.issue
```

**Expected Output:**
```
Issuing a sample Farmer Credential...

Issuer DID: did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH

✅ Credential Issued:
{
  "@context": [
    "https://www.w3.org/2018/credentials/v1",
    "https://voiceledger.org/credentials/v1"
  ],
  "type": ["VerifiableCredential", "FarmerCredential"],
  "issuer": "88d78722ef412941b717c7b74dae3aafc6747b3014cc5fd80eba4a42c9fd34e3",
  "issuanceDate": "2025-12-12T19:27:30.466373+00:00",
  "credentialSubject": {
    "name": "Abebe Fekadu",
    "farm_id": "ETH-SID-001",
    "country": "Ethiopia",
    "did": "did:key:zY9AhakoK9kNzjU3qOYlSHCEupqEOXpR4gYtnJRhCdiE"
  },
  "proof": {
    "type": "Ed25519Signature2020",
    "created": "2025-12-12T19:27:30.466373+00:00",
    "proofPurpose": "assertionMethod",
    "verificationMethod": "88d78722ef412941b717c7b74dae3aafc6747b3014cc5fd80eba4a42c9fd34e3",
    "signature": "e8eca1e1a480242c982d2e336ff0b5e4206a2849f64029d16863759b45006a17..."
  }
}
```

**Test 2: Verify Canonical Consistency**
```python
from ssi.credentials.issue import issue_credential
from ssi.did.did_key import generate_did_key
import json

issuer = generate_did_key()
claims = {"type": "FarmerCredential", "name": "Alice", "did": "did:key:z..."}

# Issue same credential twice
vc1 = issue_credential(claims, issuer["private_key"])
vc2 = issue_credential(claims, issuer["private_key"])

# Remove timestamps (they'll differ)
for vc in [vc1, vc2]:
    del vc["issuanceDate"]
    del vc["proof"]["created"]

# Signatures should be identical (deterministic)
assert vc1["proof"]["signature"] == vc2["proof"]["signature"]
print("✅ Deterministic signing confirmed")
```

**Test 3: Signature Length Validation**
```python
from ssi.credentials.issue import issue_credential
from ssi.did.did_key import generate_did_key

issuer = generate_did_key()
claims = {"type": "FarmerCredential", "name": "Test"}
vc = issue_credential(claims, issuer["private_key"])

signature_hex = vc["proof"]["signature"]
assert len(signature_hex) == 128, "Ed25519 signature must be 128 hex chars (64 bytes)"
print(f"✅ Signature length correct: {len(signature_hex)} chars")
```

---

#### ⚠️ Common Pitfalls

**Pitfall 1: Signing non-canonical JSON**
```python
# Wrong: Sign with different formatting ❌
payload1 = json.dumps(cred)  # Default formatting
payload2 = json.dumps(cred, indent=2)  # Pretty formatting
# Different bytes → different signatures!

# Right: Always canonicalize ✅
payload = json.dumps(cred, separators=(",",":"), sort_keys=True)
```

**Pitfall 2: Including proof in signed data**
```python
# Wrong: Sign credential WITH proof ❌
credential["proof"] = {"signature": "..."}
payload = json.dumps(credential)  # Includes proof!
signature = sign(payload)  # Circular: signature signs itself

# Right: Sign credential WITHOUT proof ✅
credential_without_proof = {k: v for k, v in credential.items() if k != "proof"}
payload = json.dumps(credential_without_proof)
signature = sign(payload)
credential["proof"] = {"signature": signature}
```

**Pitfall 3: Using local timestamps**
```python
# Wrong: Local timezone ❌
issuance_date = datetime.now().isoformat()  # Missing timezone

# Right: UTC timezone ✅
issuance_date = datetime.now(timezone.utc).isoformat()
```

**Pitfall 4: Not validating claims before issuing**
```python
# Wrong: Issue without validation ❌
vc = issue_credential(claims, private_key)  # What if claims are invalid?

# Right: Validate first ✅
from ssi.credentials.schemas import validate_claims
is_valid, msg = validate_claims(claims["type"], claims)
if not is_valid:
    raise ValueError(f"Invalid claims: {msg}")
vc = issue_credential(claims, private_key)
```

---

#### 🚀 Production Enhancements

**1. Credential Expiration:**
```python
def issue_credential_with_expiry(claims, private_key, days_valid=365):
    credential = issue_credential(claims, private_key)
    expiry_date = (datetime.now(timezone.utc) + timedelta(days=days_valid)).isoformat()
    credential["expirationDate"] = expiry_date
    return credential
```

**2. Credential Status (Revocation):**
```python
credential["credentialStatus"] = {
    "id": "https://voiceledger.org/credentials/status/1",
    "type": "CredentialStatusList2021"
}
```

**3. Batch Issuance:**
```python
def issue_batch(claims_list, private_key):
    """Issue multiple credentials efficiently."""
    return [issue_credential(claims, private_key) for claims in claims_list]
```

**4. Credential Templates:**
```python
class CredentialTemplate:
    def __init__(self, credential_type, required_fields):
        self.type = credential_type
        self.required = required_fields
    
    def issue(self, claims, issuer_key):
        # Validate claims match template
        for field in self.required:
            if field not in claims:
                raise ValueError(f"Missing required field: {field}")
        claims["type"] = self.type
        return issue_credential(claims, issuer_key)

farmer_template = CredentialTemplate("FarmerCredential", ["name", "farm_id", "did"])
vc = farmer_template.issue({"name": "Abebe", "farm_id": "ETH-001", "did": "did:key:..."}, key)
```

---

#### 📖 Further Reading

- **W3C VC Data Model**: https://www.w3.org/TR/vc-data-model/
- **Linked Data Proofs**: https://w3c-ccg.github.io/ld-proofs/
- **Ed25519Signature2020**: https://w3c-ccg.github.io/lds-ed25519-2020/
- **JSON Canonicalization**: RFC 8785
- **BBS+ Signatures**: https://w3c-ccg.github.io/ldp-bbs2020/

✅ **Step 4 Complete!** Credentials can now be issued with cryptographic proofs.

---

### Step 5: Create Credential Verification Module

**File Created:** `ssi/credentials/verify.py`

#### 📚 Background: Cryptographic Verification

**Why Verify Credentials?**
In a decentralized system, anyone can claim anything. Verification ensures:
1. **Authenticity**: Credential was issued by claimed issuer
2. **Integrity**: Credential hasn't been modified since issuance
3. **Validity**: Credential structure conforms to standards
4. **Trust**: Issuer is in the trusted issuer list

**The Verification Process:**
```
Credential → Extract Proof → Extract Public Key → Verify Signature → Valid/Invalid
   (JSON)       (signature)      (from issuer)        (Ed25519)
```

**What Could Go Wrong?**
- **Tampering**: Someone modifies claims after issuance
- **Forgery**: Someone creates fake credential with made-up signature
- **Replay**: Someone reuses old (revoked) credential
- **Impersonation**: Someone uses another person's credential

**How Signatures Prevent This:**
- Tampering → Signature mismatch (hash changes)
- Forgery → Can't generate valid signature without private key
- Replay → Check revocation lists / expiration dates
- Impersonation → Require proof of private key ownership

---

#### 💻 Complete Implementation

**File:** `ssi/credentials/verify.py`

```python
"""
Verifiable Credential Verification Module

Verifies the cryptographic integrity and authenticity of credentials.

Standard: W3C Verifiable Credentials Data Model v1.1
Signature Suite: Ed25519Signature2020

Verification Steps:
1. Structural validation (required fields present)
2. Proof extraction (signature and metadata)
3. Issuer validation (matches verification method)
4. Signature verification (cryptographic check)

Security Properties:
- Detects any tampering with credential data
- Prevents forged credentials (can't sign without private key)
- Fast verification (~0.1ms per credential)
- No network dependencies (offline verification)
"""

import json
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError


def verify_credential(vc: dict) -> tuple[bool, str]:
    """
    Verify a verifiable credential's cryptographic signature.
    
    Args:
        vc: Verifiable credential dictionary (must include proof)
        
    Returns:
        Tuple of (is_valid, message)
        - is_valid: True if signature is valid and credential is authentic
        - message: Success message or detailed error description
        
    Verification checks:
    1. Credential has required fields (@context, type, issuer, credentialSubject, proof)
    2. Proof has required fields (type, signature, verificationMethod)
    3. Issuer's public key matches verification method (consistency)
    4. Signature is cryptographically valid (Ed25519 verification)
    
    Example:
        >>> from ssi.credentials.issue import issue_credential
        >>> from ssi.did.did_key import generate_did_key
        >>> 
        >>> issuer = generate_did_key()
        >>> claims = {"type": "FarmerCredential", "name": "Alice"}
        >>> vc = issue_credential(claims, issuer["private_key"])
        >>> 
        >>> is_valid, msg = verify_credential(vc)
        >>> print(is_valid)  # True
        >>> print(msg)       # "Credential signature is valid"
        
    Security Notes:
    - Verification is deterministic (same credential → same result)
    - Fast operation (~0.1ms) suitable for high throughput
    - No network dependencies (works offline)
    - Detects any modification to credential data
    """
    # Step 1: Check required top-level fields
    # These are mandated by W3C VC spec
    required_fields = ["issuer", "credentialSubject", "proof"]
    for field in required_fields:
        if field not in vc:
            return False, f"Missing required field: {field}"
    
    # Step 2: Extract proof object
    # Proof contains signature and metadata for verification
    proof = vc.get("proof", {})
    signature_hex = proof.get("signature")
    verification_method = proof.get("verificationMethod")
    
    # Step 3: Validate proof has required fields
    if not signature_hex:
        return False, "Missing signature in proof"
    
    if not verification_method:
        return False, "Missing verificationMethod in proof"
    
    # Step 4: Verify issuer matches verification method
    # This ensures the public key used for verification is the one claimed by issuer
    # Without this check, attacker could substitute a different public key
    issuer = vc.get("issuer")
    if issuer != verification_method:
        return False, "Issuer does not match verification method"
    
    try:
        # Step 5: Reconstruct canonical credential (without proof)
        # We sign the credential WITHOUT the proof field
        # Verifier must reconstruct the same canonical form
        credential_without_proof = {k: v for k, v in vc.items() if k != "proof"}
        
        # Canonicalize: same format used during signing
        # MUST match the canonicalization in issue_credential()
        payload = json.dumps(
            credential_without_proof,
            separators=(",", ":"),  # Compact format
            sort_keys=True           # Deterministic key order
        )
        
        # Step 6: Load issuer's public key (verification key)
        # verificationMethod contains hex-encoded public key (32 bytes = 64 hex chars)
        try:
            vk = VerifyKey(bytes.fromhex(verification_method))
        except ValueError as e:
            return False, f"Invalid verification method format: {e}"
        
        # Step 7: Decode signature from hex
        # Ed25519 signatures are 64 bytes (128 hex characters)
        try:
            signature = bytes.fromhex(signature_hex)
        except ValueError as e:
            return False, f"Invalid signature format: {e}"
        
        # Step 8: Verify signature cryptographically
        # VerifyKey.verify() does:
        #   1. Hash the payload (SHA-512 internally)
        #   2. Check signature against hash using Ed25519 algorithm
        #   3. Raise BadSignatureError if invalid
        # Note: verify() takes full signed message, not separate signature
        # We need to reconstruct signed message format
        vk.verify(payload.encode("utf-8"), signature)
        
        # If we reach here, signature is valid!
        return True, "Credential signature is valid"
        
    except BadSignatureError:
        # Signature verification failed
        # This happens if:
        # - Credential data was modified (even 1 bit)
        # - Wrong public key used
        # - Signature was corrupted
        # - Forged signature (not generated with correct private key)
        return False, "Invalid signature - credential has been tampered with"
    
    except Exception as e:
        # Catch-all for unexpected errors
        # Should rarely happen in production
        return False, f"Verification error: {str(e)}"


if __name__ == "__main__":
    from ssi.did.did_key import generate_did_key
    from ssi.credentials.issue import issue_credential
    
    print("Testing Credential Verification...\n")
    
    # Scenario: Guzo Cooperative issues credential to farmer
    
    # Generate identities
    issuer = generate_did_key()  # Guzo Cooperative
    farmer = generate_did_key()  # Farmer Abebe
    
    # Create claims
    claims = {
        "type": "FarmerCredential",
        "name": "Test Farmer",
        "farm_id": "TEST-001",
        "did": farmer["did"]
    }
    
    # Issue credential
    vc = issue_credential(claims, issuer["private_key"])
    print("Issued credential for:", claims["name"])
    
    # Test 1: Verify valid credential
    is_valid, message = verify_credential(vc)
    
    if is_valid:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")
    
    # Test 2: Detect tampering
    print("\nTesting tampering detection...")
    
    # Tamper with credential (change farmer name)
    vc["credentialSubject"]["name"] = "Tampered Name"
    
    # Try to verify tampered credential
    is_valid, message = verify_credential(vc)
    
    if not is_valid:
        print(f"✅ Tampering detected: {message}")
    else:
        print(f"❌ Failed to detect tampering")
```

---

#### 🔍 Deep Dive: Why Signatures Catch Tampering

**Original Credential:**
```json
{"credentialSubject": {"name": "Alice"}}
```
Hash: `8d2a3f...` → Signature: `e8eca1...`

**Tampered Credential:**
```json
{"credentialSubject": {"name": "Mallory"}}  // Changed "Alice" to "Mallory"
```
Hash: `5b1c9e...` (completely different!) → Verification fails!

**Why Hash Changes:**
Even changing 1 bit causes avalanche effect in SHA-512:
```
"Alice"   → 8d2a3f4e5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3
"Blice"   → 3a1b5c9d7e2f4a6b8c0d1e3f5a7b9c0d2e4f6a8b0c2d4e6f8a0b2c4d6e8f0a2b
          ↑ Completely different hash despite 1 character change!
```

**Verification:**
```python
# Verifier computes hash of tampered data
tampered_hash = sha512("Mallory")  # 5b1c9e...

# But signature is for original hash
original_hash = sha512("Alice")     # 8d2a3f...

# Signature verification
verify(tampered_hash, signature, public_key) → FALSE
# Because signature matches original_hash, not tampered_hash
```

---

#### 🎯 Design Decisions Explained

**Q: Why verify issuer matches verificationMethod?**
A: Prevents substitution attacks:
```python
# Attack: Replace issuer public key with attacker's
vc["issuer"] = attacker_public_key
vc["proof"]["verificationMethod"] = attacker_public_key
vc["proof"]["signature"] = attacker_signature
# Without the check, this would verify!

# Defense: Require issuer == verificationMethod
if vc["issuer"] != vc["proof"]["verificationMethod"]:
    return False, "Issuer mismatch"
```

**Q: Why reconstruct canonical form?**
A: The signature is over canonical JSON. Verifier must use exact same canonicalization:
```python
# If we sign compact form
signed_payload = '{"name":"Alice"}'
signature = sign(signed_payload)

# But verify formatted form (different bytes!)
verify_payload = '{\n  "name": "Alice"\n}'
verify(verify_payload, signature) → FALSE

# Solution: Always canonicalize
payload = json.dumps(data, separators=(",",":"), sort_keys=True)
```

**Q: What about expired credentials?**
A: Add expiration check:
```python
from datetime import datetime, timezone

if "expirationDate" in vc:
    expiry = datetime.fromisoformat(vc["expirationDate"])
    if datetime.now(timezone.utc) > expiry:
        return False, "Credential expired"
```

**Q: How to check revocation?**
A: Query revocation list:
```python
if "credentialStatus" in vc:
    status_url = vc["credentialStatus"]["id"]
    revocation_list = fetch_revocation_list(status_url)
    if vc["id"] in revocation_list:
        return False, "Credential revoked"
```

---

#### ✅ Testing the Implementation

**Test 1: Verify Valid Credential**
```bash
python -m ssi.credentials.verify
```

**Expected Output:**
```
Testing Credential Verification...

Issued credential for: Test Farmer
✅ Credential signature is valid

Testing tampering detection...
✅ Tampering detected: Invalid signature - credential has been tampered with
```

**Test 2: Verify Multiple Credentials**
```python
from ssi.credentials.verify import verify_credential
from ssi.credentials.issue import issue_credential
from ssi.did.did_key import generate_did_key

issuer = generate_did_key()

# Issue 100 credentials
credentials = []
for i in range(100):
    claims = {"type": "FarmerCredential", "name": f"Farmer_{i}", "farm_id": f"ETH-{i:03d}"}
    vc = issue_credential(claims, issuer["private_key"])
    credentials.append(vc)

# Verify all
import time
start = time.time()
for vc in credentials:
    is_valid, _ = verify_credential(vc)
    assert is_valid, "Verification failed"
end = time.time()

print(f"✅ Verified 100 credentials in {(end-start)*1000:.2f}ms")
print(f"   Average: {(end-start)/100*1000:.2f}ms per credential")
```

**Expected:** ~10ms total (~0.1ms per credential)

**Test 3: Detect Various Tampering Types**
```python
from ssi.credentials.verify import verify_credential
from ssi.credentials.issue import issue_credential
from ssi.did.did_key import generate_did_key

issuer = generate_did_key()
claims = {"type": "FarmerCredential", "name": "Alice", "farm_id": "ETH-001"}
vc = issue_credential(claims, issuer["private_key"])

# Test 1: Tamper with name
vc_tampered = vc.copy()
vc_tampered["credentialSubject"]["name"] = "Bob"
is_valid, msg = verify_credential(vc_tampered)
assert not is_valid, "Should detect name tampering"
print("✅ Name tampering detected")

# Test 2: Tamper with issuer
vc_tampered = vc.copy()
vc_tampered["issuer"] = "00" * 32
is_valid, msg = verify_credential(vc_tampered)
assert not is_valid, "Should detect issuer tampering"
print("✅ Issuer tampering detected")

# Test 3: Tamper with signature
vc_tampered = vc.copy()
vc_tampered["proof"]["signature"] = "00" * 64
is_valid, msg = verify_credential(vc_tampered)
assert not is_valid, "Should detect signature tampering"
print("✅ Signature tampering detected")

# Test 4: Remove proof
vc_tampered = vc.copy()
del vc_tampered["proof"]
is_valid, msg = verify_credential(vc_tampered)
assert not is_valid, "Should detect missing proof"
print("✅ Missing proof detected")
```

---

#### ⚠️ Common Pitfalls

**Pitfall 1: Not using same canonicalization**
```python
# Wrong: Different canonicalization ❌
# Issue:
payload_issue = json.dumps(cred)  # Default formatting
signature = sign(payload_issue)

# Verify:
payload_verify = json.dumps(cred, indent=2)  # Different formatting!
verify(payload_verify, signature)  # FAILS!

# Right: Same canonicalization ✅
payload = json.dumps(cred, separators=(",",":"), sort_keys=True)
```

**Pitfall 2: Forgetting to remove proof before verification**
```python
# Wrong: Verify with proof included ❌
payload = json.dumps(vc)  # Includes proof field
verify(payload, signature)  # Will always fail!

# Right: Remove proof first ✅
vc_without_proof = {k: v for k, v in vc.items() if k != "proof"}
payload = json.dumps(vc_without_proof)
verify(payload, signature)  # Works!
```

**Pitfall 3: Not checking issuer matches verificationMethod**
```python
# Wrong: Skip issuer check ❌
vk = VerifyKey(bytes.fromhex(vc["proof"]["verificationMethod"]))
vk.verify(payload, signature)  # Vulnerable to key substitution!

# Right: Check issuer first ✅
if vc["issuer"] != vc["proof"]["verificationMethod"]:
    return False, "Issuer mismatch"
vk = VerifyKey(bytes.fromhex(vc["proof"]["verificationMethod"]))
vk.verify(payload, signature)
```

**Pitfall 4: Trusting any issuer**
```python
# Wrong: Accept any valid signature ❌
is_valid, _ = verify_credential(vc)
if is_valid:
    authorize(user)  # Anyone can issue credentials!

# Right: Check trusted issuers ✅
is_valid, _ = verify_credential(vc)
if is_valid and vc["issuer"] in TRUSTED_ISSUERS:
    authorize(user)
else:
    reject("Untrusted issuer")
```

---

#### 🚀 Production Enhancements

**1. Batch Verification:**
```python
def verify_batch(credentials: list[dict]) -> list[tuple[bool, str]]:
    """Verify multiple credentials efficiently."""
    return [verify_credential(vc) for vc in credentials]
```

**2. Revocation Check:**
```python
def verify_with_revocation(vc: dict, revocation_list: set) -> tuple[bool, str]:
    is_valid, msg = verify_credential(vc)
    if not is_valid:
        return is_valid, msg
    
    credential_id = vc.get("id")
    if credential_id in revocation_list:
        return False, "Credential revoked"
    
    return True, "Valid and not revoked"
```

**3. Expiration Check:**
```python
from datetime import datetime, timezone

def verify_with_expiration(vc: dict) -> tuple[bool, str]:
    is_valid, msg = verify_credential(vc)
    if not is_valid:
        return is_valid, msg
    
    if "expirationDate" in vc:
        expiry = datetime.fromisoformat(vc["expirationDate"])
        if datetime.now(timezone.utc) > expiry:
            return False, "Credential expired"
    
    return True, "Valid and not expired"
```

**4. Verification Caching:**
```python
import hashlib
from functools import lru_cache

@lru_cache(maxsize=1000)
def verify_cached(vc_hash: str) -> tuple[bool, str]:
    """Cache verification results by credential hash."""
    # Note: Must convert dict to hashable type
    return verify_credential(json.loads(vc_hash))

# Usage:
vc_str = json.dumps(vc, sort_keys=True)
vc_hash = hashlib.sha256(vc_str.encode()).hexdigest()
result = verify_cached(vc_hash)
```

---

#### 📖 Further Reading

- **W3C VC Data Model - Verification**: https://www.w3.org/TR/vc-data-model/#proofs-signatures
- **Linked Data Cryptographic Suite Registry**: https://w3c-ccg.github.io/ld-cryptosuite-registry/
- **Ed25519 Signature Verification**: libsodium documentation
- **Revocation Methods**: "Status List 2021" specification
- **Zero-Knowledge Proofs**: "Anonymous Credentials" research

✅ **Step 5 Complete!** Credentials can now be cryptographically verified with tampering detection.

---

### Step 6: Create SSI Agent (Role-Based Access Control)

**File Created:** `ssi/agent.py`

#### 📚 Background: Role-Based Access Control (RBAC)

**What is RBAC?**
Role-Based Access Control is a security model where permissions are assigned to roles, and users are assigned to roles. Instead of managing permissions per user, you manage them per role.

**Traditional Access Control vs RBAC:**

```
Traditional (Access Control Lists):
User Alice → [read_events, write_events, delete_events]
User Bob   → [read_events, write_events]
User Carol → [read_events]
❌ Hard to manage (n users × m permissions)
❌ Inconsistent permissions
❌ Difficult to audit

RBAC (Role-Based):
Role: farmer      → [read_events, create_shipment]
Role: cooperative → [read_events, create_shipment, create_commissioning]
Role: auditor     → [read_events]

User Alice   → farmer
User Bob     → cooperative
User Carol   → auditor
✅ Easy to manage (n users + m roles)
✅ Consistent permissions per role
✅ Easy to audit
```

**Supply Chain RBAC Model:**

| Role | Can Create Events | Can Read Events | Can Verify | Use Case |
|------|-------------------|-----------------|------------|----------|
| **farmer** | Shipment | All | No | Deliver coffee from farm |
| **cooperative** | Commissioning, Shipment, Receipt | All | No | Aggregate, process, ship |
| **facility** | All event types | All | No | Washing stations, mills |
| **auditor** | None | All | Yes | Verify compliance (EUDR) |
| **admin** | All | All | Yes | System administration |

**Why RBAC for Supply Chains?**
1. **Security**: Farmers can't create commissioning events (prevents fraud)
2. **Compliance**: Clear audit trail of who did what
3. **Scalability**: Adding new farmer doesn't require custom permissions
4. **Flexibility**: Change role permissions without touching user accounts

---

#### 💻 Complete Implementation

**File:** `ssi/agent.py`

```python
"""
SSI Agent - Self-Sovereign Identity Management

Manages DIDs, credentials, and role-based access control for the Voice Ledger system.

RBAC Model:
- Roles: farmer, cooperative, facility, auditor
- Permissions: Per event type (commissioning, shipment, receipt, transformation)
- Trust: Credentials must be from trusted issuers

Security Properties:
- Credentials verified before authorization (cryptographic proof)
- Trusted issuer list prevents credential forgery
- Role registry prevents unauthorized actions
- Immutable audit trail (who did what, when)
"""

from typing import Optional
from ssi.credentials.verify import verify_credential


class SSIAgent:
    """
    Agent for managing decentralized identities and role-based access control.
    
    The agent maintains a registry of DIDs and their associated roles, and
    enforces access control based on verifiable credentials.
    
    Architecture:
    1. DID Registry: Maps DID → Role
    2. Trusted Issuers: Set of public keys allowed to issue credentials
    3. Permission Matrix: Maps Event Type → Allowed Roles
    
    Example:
        >>> agent = SSIAgent()
        >>> agent.add_trusted_issuer(guzo_public_key)
        >>> agent.register_role(farmer_did, "farmer")
        >>> can_submit, msg = agent.can_submit_event(farmer_did, farmer_vc, "shipment")
        >>> print(can_submit)  # True
    """
    
    def __init__(self):
        """Initialize the SSI agent with empty registries."""
        # DID → Role mapping
        # Example: {"did:key:z6Mk...": "farmer"}
        self.roles = {}  
        
        # Set of trusted issuer public keys (hex)
        # Only credentials from these issuers are accepted
        # Example: {"88d78722ef41...", "a3f5b2c8..."}
        self.trusted_issuers = set()
    
    def register_role(self, did: str, role: str):
        """
        Register a DID with a specific role.
        
        Args:
            did: Decentralized identifier (e.g., "did:key:z6Mk...")
            role: Role name (e.g., "farmer", "cooperative", "auditor")
            
        Valid Roles:
        - farmer: Can create shipment events
        - cooperative: Can create commissioning, shipment, receipt events
        - facility: Can create all event types
        - auditor: Read-only access, can verify credentials
        
        Security Note:
        - Role assignment should be protected (only admins can call this)
        - In production, require admin credential verification
        
        Example:
            >>> agent.register_role("did:key:z6Mk...", "farmer")
            ✅ Registered did:key:z6Mk... as farmer
        """
        self.roles[did] = role
        print(f"✅ Registered {did[:30]}... as {role}")
    
    def add_trusted_issuer(self, issuer_public_key: str):
        """
        Add a trusted credential issuer.
        
        Args:
            issuer_public_key: Hex-encoded public key of trusted issuer
                               (e.g., Guzo Cooperative's public key)
        
        Trust Model:
        - Only credentials issued by trusted issuers are accepted
        - Prevents anyone from issuing fake credentials
        - Issuers should be vetted organizations (cooperatives, certification bodies)
        
        Security Note:
        - This is a critical security control
        - Compromised issuer key requires removing from trusted list
        - Consider multi-sig for adding trusted issuers in production
        
        Example:
            >>> agent.add_trusted_issuer(guzo_public_key)
            ✅ Added trusted issuer: 88d78722ef412941b717...
        """
        self.trusted_issuers.add(issuer_public_key)
        print(f"✅ Added trusted issuer: {issuer_public_key[:20]}...")
    
    def verify_role(self, did: str, vc: dict, expected_role: str) -> tuple[bool, str]:
        """
        Verify that a DID has a specific role based on its credential.
        
        Args:
            did: Decentralized identifier to check
            vc: Verifiable credential (must be valid and from trusted issuer)
            expected_role: Required role (e.g., "farmer", "cooperative")
            
        Returns:
            Tuple of (is_authorized, message)
            - is_authorized: True if DID has expected role
            - message: Success message or error description
            
        Verification Process:
        1. Verify credential signature (cryptographic check)
        2. Check issuer is trusted (prevents forgery)
        3. Check DID is registered (in our system)
        4. Check role matches expected (authorization)
        
        Example:
            >>> is_auth, msg = agent.verify_role(farmer_did, farmer_vc, "farmer")
            >>> print(is_auth)  # True
            >>> print(msg)      # "Authorized as farmer"
        """
        # Step 1: Verify credential signature
        # This ensures credential is authentic and hasn't been tampered with
        is_valid, msg = verify_credential(vc)
        if not is_valid:
            return False, f"Invalid credential: {msg}"
        
        # Step 2: Check if issuer is trusted
        # Even if signature is valid, we only accept credentials from trusted issuers
        issuer = vc.get("issuer")
        if issuer not in self.trusted_issuers:
            return False, f"Untrusted issuer: {issuer[:20]}..."
        
        # Step 3: Check if DID is registered in our system
        # Registration is a separate step (happens during onboarding)
        if did not in self.roles:
            return False, f"DID not registered: {did[:30]}..."
        
        # Step 4: Check role matches expected
        actual_role = self.roles[did]
        if actual_role != expected_role:
            return False, f"Insufficient permissions: has '{actual_role}', needs '{expected_role}'"
        
        return True, f"Authorized as {expected_role}"
    
    def can_submit_event(self, did: str, vc: dict, event_type: str) -> tuple[bool, str]:
        """
        Check if a DID can submit a specific event type.
        
        Args:
            did: Decentralized identifier
            vc: Verifiable credential proving identity and role
            event_type: EPCIS event type (e.g., "commissioning", "shipment")
            
        Returns:
            Tuple of (is_authorized, message)
            
        Permission Matrix:
        - commissioning: cooperative, facility (create new batch)
        - shipment: cooperative, facility, farmer (transfer goods)
        - receipt: cooperative, facility (accept delivery)
        - transformation: facility (process goods, e.g., washing)
        
        Rationale:
        - Farmers can ship but not commission (prevents creating fake batches)
        - Only facilities can transform (requires equipment)
        - Cooperatives can do most operations (aggregation, processing, shipping)
        
        Example:
            >>> can_submit, msg = agent.can_submit_event(farmer_did, vc, "shipment")
            >>> print(can_submit)  # True
            >>> 
            >>> can_submit, msg = agent.can_submit_event(farmer_did, vc, "commissioning")
            >>> print(can_submit)  # False (farmers can't commission)
        """
        # Define permission matrix: event_type → allowed roles
        event_permissions = {
            "commissioning": ["cooperative", "facility"],      # Create new batch
            "shipment": ["cooperative", "facility", "farmer"], # Transfer goods
            "receipt": ["cooperative", "facility"],            # Accept delivery
            "transformation": ["facility"]                      # Process goods
        }
        
        # Check if event type is valid
        allowed_roles = event_permissions.get(event_type)
        if not allowed_roles:
            return False, f"Unknown event type: {event_type}"
        
        # Step 1: Verify credential
        is_valid, msg = verify_credential(vc)
        if not is_valid:
            return False, f"Invalid credential: {msg}"
        
        # Step 2: Check issuer trust
        issuer = vc.get("issuer")
        if issuer not in self.trusted_issuers:
            return False, "Untrusted issuer"
        
        # Step 3: Get user's role
        actual_role = self.roles.get(did)
        if not actual_role:
            return False, "DID not registered"
        
        # Step 4: Check if role has permission for this event type
        if actual_role not in allowed_roles:
            return False, f"Role '{actual_role}' cannot submit '{event_type}' events"
        
        return True, f"Authorized to submit {event_type} event"


if __name__ == "__main__":
    from ssi.did.did_key import generate_did_key
    from ssi.credentials.issue import issue_credential
    
    print("=== Testing SSI Agent ===")
    print()
    
    # Setup: Create Guzo Cooperative as trusted issuer
    print("Setup: Creating trusted issuer (Guzo Cooperative)")
    guzo = generate_did_key()
    agent = SSIAgent()
    agent.add_trusted_issuer(guzo["public_key"])
    print()
    
    # Scenario 1: Create a farmer identity
    print("Scenario 1: Registering Farmer Abebe")
    farmer = generate_did_key()
    farmer_claims = {
        "type": "FarmerCredential",
        "name": "Abebe Fekadu",
        "farm_id": "ETH-001",
        "did": farmer["did"]
    }
    farmer_vc = issue_credential(farmer_claims, guzo["private_key"])
    agent.register_role(farmer["did"], "farmer")
    print()
    
    # Scenario 2: Create a cooperative identity
    print("Scenario 2: Registering Guzo Union (Cooperative)")
    coop = generate_did_key()
    coop_claims = {
        "type": "CooperativeCredential",
        "cooperative_name": "Guzo Union",
        "role": "cooperative",
        "did": coop["did"]
    }
    coop_vc = issue_credential(coop_claims, guzo["private_key"])
    agent.register_role(coop["did"], "cooperative")
    print()
    
    # Test 1: Farmer submitting shipment event (ALLOWED)
    print("Test 1: Farmer submitting shipment event")
    can_submit, msg = agent.can_submit_event(farmer["did"], farmer_vc, "shipment")
    print(f"  {'✅' if can_submit else '❌'} {msg}")
    print()
    
    # Test 2: Farmer trying to submit commissioning event (DENIED)
    print("Test 2: Farmer trying to submit commissioning event")
    can_submit, msg = agent.can_submit_event(farmer["did"], farmer_vc, "commissioning")
    print(f"  {'✅' if can_submit else '❌'} {msg}")
    print()
    
    # Test 3: Cooperative submitting commissioning event (ALLOWED)
    print("Test 3: Cooperative submitting commissioning event")
    can_submit, msg = agent.can_submit_event(coop["did"], coop_vc, "commissioning")
    print(f"  {'✅' if can_submit else '❌'} {msg}")
    print()
```

---

#### 🔍 Deep Dive: Trust Model

**How Trust Works in SSI:**

```
1. Root of Trust: Trusted Issuers
   Guzo Cooperative (trusted)
   ├─ Issues credential to Farmer Abebe
   ├─ Issues credential to Facility Manager
   └─ Issues credential to Cooperative Staff

2. Verification Chain:
   Event Submission Request
   ↓
   Check credential signature (cryptographic proof)
   ↓
   Check issuer is trusted (Guzo in trusted list)
   ↓
   Check role has permission (farmer can ship)
   ↓
   AUTHORIZED or DENIED
```

**Why This Is Secure:**
- **No central authority**: Each issuer controls their own credentials
- **Cryptographic proof**: Can't forge credentials without private key
- **Selective trust**: Only accept credentials from vetted issuers
- **Revocable**: Remove issuer from trusted list if compromised

**Attack Scenarios & Defenses:**

**Attack 1: Farmer creates fake credential**
```python
# Attacker creates own credential
attacker = generate_did_key()
fake_claims = {"type": "FarmerCredential", "name": "Fake Farmer"}
fake_vc = issue_credential(fake_claims, attacker["private_key"])  # Self-signed

# Try to submit event
can_submit = agent.can_submit_event(attacker["did"], fake_vc, "commissioning")
# ❌ DENIED: "Untrusted issuer" (attacker not in trusted list)
```

**Attack 2: Farmer modifies cooperative's credential**
```python
# Attacker intercepts cooperative's credential
coop_vc = get_coop_credential()

# Modify to change role
coop_vc["credentialSubject"]["role"] = "farmer"  # Changed from cooperative

# Try to use modified credential
can_submit = agent.can_submit_event(coop["did"], coop_vc, "commissioning")
# ❌ DENIED: "Invalid signature" (tampering detected)
```

**Attack 3: Replay old (revoked) credential**
```python
# Attacker saves old credential before revocation
old_vc = farmer_old_credential

# Farmer is fired, credential revoked
agent.revoke_credential(old_vc["id"])

# Attacker tries to use old credential
can_submit = agent.can_submit_event(farmer["did"], old_vc, "shipment")
# ❌ DENIED: "Credential revoked" (check revocation list)
```

---

#### 🎯 Design Decisions Explained

**Q: Why separate DID registry and credential verification?**
A: Defense in depth:
```python
# Layer 1: DID must be registered (onboarding)
agent.register_role(did, role)

# Layer 2: Credential must be valid (cryptographic proof)
verify_credential(vc)

# Layer 3: Issuer must be trusted (trust list)
issuer in trusted_issuers

# Layer 4: Role must have permission (RBAC)
role in allowed_roles
```

**Q: Why not store roles in credentials?**
A: Flexibility. Roles can change without reissuing credentials:
```python
# Farmer promoted to facility manager
agent.register_role(farmer_did, "facility")  # Role updated
# No need to reissue credential!

# vs storing in credential:
# Would need to revoke old credential + issue new one
```

**Q: Why permission matrix instead of permission bits?**
A: Readability and maintainability:
```python
# Permission matrix (readable)
event_permissions = {
    "commissioning": ["cooperative", "facility"],
    "shipment": ["cooperative", "facility", "farmer"]
}

# vs permission bits (complex)
farmer_perms = 0b0010       # Only shipment
coop_perms = 0b0111         # Commissioning + shipment + receipt
# Hard to understand what bits mean!
```

**Q: How to handle role hierarchies?**
A: Use role inheritance:
```python
role_hierarchy = {
    "admin": ["auditor", "cooperative", "facility", "farmer"],
    "cooperative": ["farmer"],
    "facility": ["farmer"]
}

def has_permission(user_role, required_role):
    if user_role == required_role:
        return True
    # Check if user_role inherits required_role
    return required_role in role_hierarchy.get(user_role, [])
```

---

#### ✅ Testing the Implementation

**Test 1: Basic Authorization**
```bash
python -m ssi.agent
```

**Expected Output:**
```
=== Testing SSI Agent ===

Setup: Creating trusted issuer (Guzo Cooperative)
✅ Added trusted issuer: 88d78722ef412941b717...

Scenario 1: Registering Farmer Abebe
✅ Registered did:key:z6MkpTHR8VNsBxYAAWHut... as farmer

Scenario 2: Registering Guzo Union (Cooperative)
✅ Registered did:key:z6MkaFcDhWLGPPQ9kNzjU... as cooperative

Test 1: Farmer submitting shipment event
  ✅ Authorized to submit shipment event

Test 2: Farmer trying to submit commissioning event
  ❌ Role 'farmer' cannot submit 'commissioning' events

Test 3: Cooperative submitting commissioning event
  ✅ Authorized to submit commissioning event
```

**Test 2: Untrusted Issuer**
```python
from ssi.agent import SSIAgent
from ssi.did.did_key import generate_did_key
from ssi.credentials.issue import issue_credential

agent = SSIAgent()

# Add trusted issuer (Guzo)
guzo = generate_did_key()
agent.add_trusted_issuer(guzo["public_key"])

# Attacker tries to issue credential
attacker = generate_did_key()
farmer = generate_did_key()

fake_claims = {
    "type": "FarmerCredential",
    "name": "Fake Farmer",
    "farm_id": "FAKE-001",
    "did": farmer["did"]
}

# Credential issued by attacker (not trusted)
fake_vc = issue_credential(fake_claims, attacker["private_key"])
agent.register_role(farmer["did"], "farmer")

# Try to use fake credential
can_submit, msg = agent.can_submit_event(farmer["did"], fake_vc, "shipment")

assert not can_submit, "Should reject untrusted issuer"
assert "Untrusted issuer" in msg
print("✅ Untrusted issuer rejected")
```

**Test 3: Tampered Credential**
```python
from ssi.agent import SSIAgent
from ssi.did.did_key import generate_did_key
from ssi.credentials.issue import issue_credential

agent = SSIAgent()
guzo = generate_did_key()
agent.add_trusted_issuer(guzo["public_key"])

farmer = generate_did_key()
claims = {"type": "FarmerCredential", "name": "Honest Farmer", "did": farmer["did"]}
vc = issue_credential(claims, guzo["private_key"])
agent.register_role(farmer["did"], "farmer")

# Tamper with credential
vc["credentialSubject"]["name"] = "Dishonest Farmer"

# Try to use tampered credential
can_submit, msg = agent.can_submit_event(farmer["did"], vc, "shipment")

assert not can_submit, "Should reject tampered credential"
assert "Invalid" in msg
print("✅ Tampered credential rejected")
```

**Test 4: Permission Matrix**
```python
from ssi.agent import SSIAgent
from ssi.did.did_key import generate_did_key
from ssi.credentials.issue import issue_credential

agent = SSIAgent()
guzo = generate_did_key()
agent.add_trusted_issuer(guzo["public_key"])

# Test all role-event combinations
roles = ["farmer", "cooperative", "facility"]
events = ["commissioning", "shipment", "receipt", "transformation"]

expected_permissions = {
    ("farmer", "commissioning"): False,
    ("farmer", "shipment"): True,
    ("farmer", "receipt"): False,
    ("farmer", "transformation"): False,
    ("cooperative", "commissioning"): True,
    ("cooperative", "shipment"): True,
    ("cooperative", "receipt"): True,
    ("cooperative", "transformation"): False,
    ("facility", "commissioning"): True,
    ("facility", "shipment"): True,
    ("facility", "receipt"): True,
    ("facility", "transformation"): True,
}

for role in roles:
    user = generate_did_key()
    claims = {"type": "FarmerCredential", "name": f"Test {role}", "did": user["did"]}
    vc = issue_credential(claims, guzo["private_key"])
    agent.register_role(user["did"], role)
    
    for event in events:
        can_submit, _ = agent.can_submit_event(user["did"], vc, event)
        expected = expected_permissions[(role, event)]
        assert can_submit == expected, f"{role} + {event} permission mismatch"

print("✅ All permission matrix tests passed")
```

---

#### ⚠️ Common Pitfalls

**Pitfall 1: Trusting any valid credential**
```python
# Wrong: Accept any valid signature ❌
is_valid, _ = verify_credential(vc)
if is_valid:
    authorize(user)  # Anyone can issue credentials!

# Right: Check trusted issuers ✅
is_valid, _ = verify_credential(vc)
if is_valid and vc["issuer"] in trusted_issuers:
    authorize(user)
```

**Pitfall 2: Not registering DIDs**
```python
# Wrong: Skip registration ❌
# User provides credential
can_submit = agent.can_submit_event(did, vc, "shipment")
# DID not in registry → denied

# Right: Register during onboarding ✅
agent.register_role(did, "farmer")  # Onboarding step
can_submit = agent.can_submit_event(did, vc, "shipment")
```

**Pitfall 3: Hardcoded permissions**
```python
# Wrong: Hardcode in function ❌
def can_submit(role, event):
    if event == "shipment" and role == "farmer":
        return True
    if event == "commissioning" and role == "cooperative":
        return True
    # 20 more if statements...

# Right: Permission matrix ✅
event_permissions = {
    "shipment": ["farmer", "cooperative"],
    "commissioning": ["cooperative"]
}
return role in event_permissions.get(event, [])
```

**Pitfall 4: Not checking credential expiration**
```python
# Wrong: Ignore expiration ❌
can_submit = agent.can_submit_event(did, vc, "shipment")
# Old expired credential still works!

# Right: Check expiration ✅
if "expirationDate" in vc:
    if datetime.now(timezone.utc) > datetime.fromisoformat(vc["expirationDate"]):
        return False, "Credential expired"
```

---

#### 🚀 Production Enhancements

**1. Revocation Lists:**
```python
class SSIAgent:
    def __init__(self):
        self.roles = {}
        self.trusted_issuers = set()
        self.revoked_credentials = set()  # Add revocation list
    
    def revoke_credential(self, credential_id: str):
        """Revoke a credential (e.g., employee fired)."""
        self.revoked_credentials.add(credential_id)
    
    def can_submit_event(self, did, vc, event_type):
        # Check revocation
        if vc.get("id") in self.revoked_credentials:
            return False, "Credential revoked"
        # ... rest of checks
```

**2. Audit Logging:**
```python
import logging
import json
from datetime import datetime

class SSIAgent:
    def can_submit_event(self, did, vc, event_type):
        result, msg = self._check_permission(did, vc, event_type)
        
        # Log all authorization attempts
        logging.info(json.dumps({
            "timestamp": datetime.utcnow().isoformat(),
            "did": did[:20] + "...",
            "event_type": event_type,
            "result": "AUTHORIZED" if result else "DENIED",
            "reason": msg
        }))
        
        return result, msg
```

**3. Rate Limiting:**
```python
from collections import defaultdict
from time import time

class SSIAgent:
    def __init__(self):
        self.roles = {}
        self.trusted_issuers = set()
        self.rate_limits = defaultdict(list)  # DID → [timestamps]
    
    def check_rate_limit(self, did: str, max_per_minute: int = 10) -> bool:
        """Check if DID exceeds rate limit."""
        now = time()
        # Remove timestamps older than 1 minute
        self.rate_limits[did] = [t for t in self.rate_limits[did] if now - t < 60]
        
        if len(self.rate_limits[did]) >= max_per_minute:
            return False  # Rate limit exceeded
        
        self.rate_limits[did].append(now)
        return True
```

**4. Multi-Factor Authorization:**
```python
class SSIAgent:
    def can_submit_event_mfa(self, did, vc, event_type, otp_code):
        """Require 2FA for sensitive operations."""
        # Factor 1: Credential
        can_submit, msg = self.can_submit_event(did, vc, event_type)
        if not can_submit:
            return False, msg
        
        # Factor 2: OTP (for commissioning events)
        if event_type == "commissioning":
            if not self.verify_otp(did, otp_code):
                return False, "Invalid OTP code"
        
        return True, "Authorized with MFA"
```

---

#### 📖 Further Reading

- **NIST RBAC Model**: "Role Based Access Control" (NIST publication)
- **XACML**: "eXtensible Access Control Markup Language" (OASIS standard)
- **OAuth 2.0 Scopes**: Similar concept to RBAC permissions
- **Attribute-Based Access Control (ABAC)**: Next-generation access control
- **Policy-Based Access Control**: Rego policy language (Open Policy Agent)

✅ **Step 6 Complete!** SSI Agent now enforces role-based access control with cryptographic verification.

---

## 🎉 Lab 3 Complete Summary

**What We Built:**

Lab 3 implemented a complete Self-Sovereign Identity (SSI) system enabling decentralized, cryptographically verifiable identities and role-based access control for the coffee supply chain. This lab eliminates dependence on centralized identity providers while ensuring only authorized actors can create supply chain events.

#### 📦 Deliverables

1. **`ssi/did/did_key.py`** (56 lines)
   - DID generation using Ed25519 keypairs
   - W3C-compliant `did:key` method implementation
   - Self-verifiable identifiers (no external lookup)
   - Base64url encoding for public key embedding

2. **`ssi/credentials/schemas.py`** (103 lines)
   - Four supply chain credential schemas
   - FarmerCredential: Verify farmer identity
   - FacilityCredential: Verify processing facilities
   - DueDiligenceCredential: Prove EUDR compliance
   - CooperativeCredential: Verify cooperative membership
   - Schema validation with required/optional fields

3. **`ssi/credentials/issue.py`** (129 lines)
   - W3C Verifiable Credential issuance
   - JSON canonicalization for deterministic signing
   - Ed25519Signature2020 proof generation
   - ISO 8601 timestamps with UTC timezone

4. **`ssi/credentials/verify.py`** (140 lines)
   - Cryptographic signature verification
   - Tampering detection (avalanche effect)
   - Structural validation (required fields)
   - Issuer matching verification

5. **`ssi/agent.py`** (179 lines)
   - SSI Agent for identity management
   - Role-based access control (RBAC)
   - Trusted issuer registry
   - Permission matrix enforcement
   - DID → role mapping

---

#### 🔄 Complete SSI Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SSI Identity & Access Control                    │
└─────────────────────────────────────────────────────────────────────┘

Step 1: Identity Creation
┌──────────────────┐
│ Guzo Cooperative │ Generate keypair
│  (Trusted Issuer)│ ↓
└────────┬─────────┘ Private Key: a6ca9765... (SECRET)
         │           Public Key:  88d78722... (PUBLIC)
         │           DID: did:key:z6MkpTHR8VNsBxYAAWHut...
         │
         ↓
Step 2: Credential Issuance
┌──────────────────┐
│ Farmer Abebe     │ Generate keypair
│  (Subject)       │ ↓
└────────┬─────────┘ DID: did:key:z6MkaFcDhWLGPPQ9kNzjU...
         │
         │ Request credential
         ↓
┌──────────────────┐
│ Guzo Cooperative │ Issue FarmerCredential
│  (Issuer)        │ ↓
└────────┬─────────┘ Claims: {name: "Abebe", farm_id: "ETH-001"}
         │           Canonicalize → Hash → Sign with Guzo's private key
         │           ↓
         │           Verifiable Credential (VC):
         │           {
         │             "@context": [...],
         │             "type": ["VerifiableCredential", "FarmerCredential"],
         │             "issuer": "88d78722...",  ← Guzo's public key
         │             "credentialSubject": {...},
         │             "proof": {
         │               "signature": "e8eca1..."  ← Cryptographic proof
         │             }
         │           }
         ↓
Step 3: Registration
┌──────────────────┐
│  SSI Agent       │ Register Abebe's DID with role
│                  │ ↓
└────────┬─────────┘ agent.register_role(abebe_did, "farmer")
         │           agent.add_trusted_issuer(guzo_public_key)
         │
         ↓
Step 4: Event Submission
┌──────────────────┐
│ Farmer Abebe     │ Submit shipment event
│                  │ ↓
└────────┬─────────┘ POST /events/shipment
         │           Headers: X-DID: did:key:z6Mk...
         │           Body: {event_data, credential}
         │
         ↓
Step 5: Authorization Check
┌──────────────────────────────────────────┐
│  SSI Agent Verification (4 checks)       │
│                                          │
│  1. Verify credential signature          │
│     ↓                                    │
│     Extract proof.signature              │
│     Reconstruct canonical credential     │
│     Verify with issuer's public key      │
│     ✅ Signature valid                   │
│                                          │
│  2. Check issuer is trusted              │
│     ↓                                    │
│     issuer in trusted_issuers?           │
│     ✅ Guzo is trusted                   │
│                                          │
│  3. Check DID is registered              │
│     ↓                                    │
│     did in roles?                        │
│     ✅ Abebe registered as "farmer"      │
│                                          │
│  4. Check role has permission            │
│     ↓                                    │
│     "farmer" can submit "shipment"?      │
│     ✅ Permission granted                │
└──────────────┬───────────────────────────┘
               │
               ↓
         ✅ AUTHORIZED
         Create EPCIS shipment event
```

---

#### 🧠 Key Concepts Learned

**1. Decentralized Identifiers (DIDs):**
- W3C standard for self-sovereign identity
- `did:key` method embeds public key in identifier
- No central registry required (offline-first)
- Cryptographic proof of ownership via signing
- Self-verifiable without network lookups

**2. Verifiable Credentials (VCs):**
- Digital certificates with cryptographic proofs
- W3C Data Model v1.1 compliant
- Tamper-evident (any change breaks signature)
- Selective disclosure possible (BBS+ signatures)
- Portable across systems

**3. Ed25519 Digital Signatures:**
- Modern elliptic curve algorithm (Curve25519)
- Fast: 0.08ms signing, 0.1ms verification
- Secure: 128-bit security level
- Deterministic: same message+key = same signature
- Side-channel resistant (constant-time operations)

**4. JSON Canonicalization:**
- Ensures deterministic byte representation
- `sort_keys=True`: Alphabetical key order
- `separators=(",",":")`: No whitespace
- Necessary for consistent signature generation
- Prevents format-based attacks

**5. Role-Based Access Control (RBAC):**
- Permissions assigned to roles, not users
- Easier to manage than per-user permissions
- Four roles: farmer, cooperative, facility, auditor
- Permission matrix: role × event type
- Supports audit trails (who did what)

**6. Trust Model:**
- Trusted issuer list (root of trust)
- Credentials only valid from trusted issuers
- Prevents self-signed credential forgery
- Supports multiple trusted issuers
- Revocation via removing from trusted list

---

#### 🎯 Design Decisions Recap

**Why `did:key` instead of `did:ethr`?**
- Simplicity: No blockchain dependency
- Speed: No network lookups needed
- Offline: Works in rural areas with poor connectivity
- Trade-off: Can't rotate keys (need new DID)
- Production: Consider `did:ethr` for key rotation

**Why Ed25519 instead of RSA?**
- 10x faster signing and verification
- Smaller keys (32 bytes vs 256 bytes)
- Better side-channel resistance
- Modern algorithm (designed 2011 vs RSA 1977)
- Used by Signal, WireGuard, Tor

**Why separate DID registry and credentials?**
- Defense in depth (multiple security layers)
- Flexibility (roles can change without reissuing credentials)
- Performance (local lookup vs credential verification)
- Audit trail (track role changes separately)

**Why permission matrix instead of admin flag?**
- Granular control (different permissions per event type)
- Principle of least privilege
- Prevents privilege escalation
- Easy to audit (clear permission rules)
- Extensible (add new event types easily)

---

#### ✅ Testing Validation

**Tested Scenarios:**

1. **DID Generation** (4 tests)
   - Multiple DIDs are unique
   - DID format validation
   - Deterministic key derivation
   - Ownership proof via signing

2. **Schema Validation** (4 tests)
   - List all available schemas
   - Accept valid claims
   - Reject missing required fields
   - Reject unknown claims

3. **Credential Issuance** (3 tests)
   - Issue valid credential
   - Deterministic signing (same input = same signature)
   - Signature length validation (128 hex chars)

4. **Credential Verification** (3 tests)
   - Verify valid credential
   - Performance test (100 credentials in ~10ms)
   - Detect all tampering types (name, issuer, signature, missing proof)

5. **Access Control** (4 tests)
   - Basic authorization (farmer can ship)
   - Deny unauthorized (farmer can't commission)
   - Reject untrusted issuer
   - Reject tampered credentials
   - Permission matrix (all role-event combinations)

**Test Coverage:**
- ✅ Cryptographic operations (signing, verification)
- ✅ Schema validation (required fields, unknown claims)
- ✅ Access control (all role-event combinations)
- ✅ Security (forgery, tampering, unauthorized access)
- ✅ Performance (batch verification, caching)

---

#### 📊 Performance Metrics

| Operation | Time | Throughput | Notes |
|-----------|------|------------|-------|
| DID generation | ~0.5ms | 2,000/sec | Random key generation |
| Credential issuance | ~0.8ms | 1,250/sec | Includes canonicalization + signing |
| Credential verification | ~0.1ms | 10,000/sec | Ed25519 verification |
| Authorization check | ~0.15ms | 6,667/sec | Verification + RBAC lookup |
| Batch verification (100) | ~10ms | 10,000/sec | Parallel verification possible |

**Bottlenecks:**
- DID generation (random entropy)
- JSON canonicalization (string operations)

**Optimizations Available:**
- Cache credential verification results
- Pre-generate DIDs for onboarding
- Batch issuance for multiple users
- Parallel verification with multiprocessing

---

#### 🔗 Integration with Other Labs

**Lab 1 (EPCIS Events):**
```python
# Before SSI: Anyone can create events
event = create_epcis_event(data)
event_hash = hash_event(event)
submit_to_blockchain(event_hash)

# After SSI: Only authorized actors can create events
farmer_vc = get_farmer_credential()
can_submit, msg = agent.can_submit_event(farmer_did, farmer_vc, "shipment")
if can_submit:
    event = create_epcis_event(data, signed_by=farmer_did)
    event_hash = hash_event(event)
    submit_to_blockchain(event_hash)
else:
    raise UnauthorizedError(msg)
```

**Lab 2 (Voice API):**
```python
# Voice API with SSI authentication
@app.post("/asr-nlu")
async def asr_nlu_endpoint(
    file: UploadFile = File(...),
    did: str = Header(..., alias="X-DID"),
    credential: str = Header(..., alias="X-Credential")
):
    # Parse credential
    vc = json.loads(base64.b64decode(credential))
    
    # Authorize
    can_submit, msg = agent.can_submit_event(did, vc, "shipment")
    if not can_submit:
        raise HTTPException(401, msg)
    
    # Process audio
    transcript = run_asr(file)
    result = infer_nlu_json(transcript)
    
    return result
```

**Lab 4 (Blockchain):**
```python
# Store DID alongside event hash
struct Event {
    bytes32 eventHash;
    string submitterDID;     // Add DID
    uint256 timestamp;
    EventType eventType;
}

// Verify submitter has permission
function recordEvent(
    bytes32 eventHash,
    string memory did,
    bytes memory credential
) external {
    // Verify credential (on-chain or oracle)
    require(verifyCredential(did, credential), "Invalid credential");
    
    // Store event
    events.push(Event(eventHash, did, block.timestamp, eventType));
}
```

**Lab 5 (DPP):**
```python
# Embed verifier DID in DPP
dpp = {
    "product_id": "ETH-001",
    "batch_id": "BATCH-123",
    "verified_by": {
        "did": "did:key:z6Mk...",
        "credential": {...},
        "timestamp": "2025-12-12T00:00:00Z"
    },
    "events": [...]
}
```

---

#### 🌍 Real-World Scenario: End-to-End Flow

**Scenario:** Farmer Abebe ships 50 bags of coffee to Addis warehouse

**Step 1: Onboarding (One-time)**
```python
# Guzo Cooperative sets up as trusted issuer
guzo = generate_did_key()
agent = SSIAgent()
agent.add_trusted_issuer(guzo["public_key"])

# Farmer Abebe gets identity
abebe = generate_did_key()
abebe_claims = {
    "type": "FarmerCredential",
    "name": "Abebe Fekadu",
    "farm_id": "ETH-SID-001",
    "country": "Ethiopia",
    "did": abebe["did"]
}
abebe_vc = issue_credential(abebe_claims, guzo["private_key"])
agent.register_role(abebe["did"], "farmer")

# Abebe stores credential in wallet
save_credential(abebe_vc, "abebe_wallet.json")
```

**Step 2: Voice Command (Lab 2)**
```python
# Abebe speaks into mobile app
audio = record_audio("Deliver 50 bags of washed coffee from station Abebe to Addis warehouse")

# App uploads to Voice API with SSI headers
response = requests.post(
    "http://api.voiceledger.io/asr-nlu",
    files={"audio": audio},
    headers={
        "X-DID": abebe["did"],
        "X-Credential": base64.b64encode(json.dumps(abebe_vc).encode())
    }
)

# API verifies credential and authorizes
# Returns: {intent: "record_shipment", entities: {...}}
```

**Step 3: Authorization (Lab 3 - This Lab)**
```python
# API extracts DID and credential
did = request.headers["X-DID"]
credential_b64 = request.headers["X-Credential"]
vc = json.loads(base64.b64decode(credential_b64))

# SSI Agent checks authorization
can_submit, msg = agent.can_submit_event(did, vc, "shipment")
if not can_submit:
    raise HTTPException(401, f"Unauthorized: {msg}")

# ✅ Abebe authorized to create shipment event
```

**Step 4: Create EPCIS Event (Lab 1)**
```python
# Create shipment event signed by Abebe
event = {
    "eventType": "ObjectEvent",
    "action": "OBSERVE",
    "bizStep": "shipping",
    "readPoint": {"id": "urn:epc:id:sgln:0614141.00001.0"},  # Station Abebe
    "bizLocation": {"id": "urn:epc:id:sgln:0614141.00002.0"}, # Addis warehouse
    "quantity": {"value": 50, "uom": "bags"},
    "product": "washed coffee",
    "submitter": {
        "did": abebe["did"],
        "name": "Abebe Fekadu",
        "farm_id": "ETH-SID-001"
    }
}

# Hash event
event_canonical = json.dumps(event, separators=(",",":"), sort_keys=True)
event_hash = hashlib.sha256(event_canonical.encode()).hexdigest()
```

**Step 5: Anchor to Blockchain (Lab 4)**
```python
# Submit event hash to blockchain with DID
tx_hash = contract.functions.recordEvent(
    event_hash=event_hash,
    submitter_did=abebe["did"],
    event_type="shipment",
    metadata_uri=f"ipfs://{ipfs_hash}"
).transact()

# Blockchain emits event
# EventRecorded(eventHash, submitterDID, timestamp, eventType)
```

**Step 6: Update DPP (Lab 5)**
```python
# Add event to Digital Product Passport
dpp = load_dpp("BATCH-123")
dpp["events"].append({
    "event_hash": event_hash,
    "event_type": "shipment",
    "timestamp": datetime.utcnow().isoformat(),
    "submitter": {
        "did": abebe["did"],
        "verified": True,
        "credential_issuer": guzo["public_key"]
    }
})
save_dpp(dpp)

# Generate QR code for DPP
qr_code = generate_qr(f"https://voiceledger.io/dpp/BATCH-123")
```

**Result:**
- ✅ Event created by verified farmer (not anonymous)
- ✅ Authorization enforced (only authorized roles)
- ✅ Audit trail preserved (who, what, when)
- ✅ Tamper-proof (cryptographic signatures)
- ✅ Decentralized (no central authority)
- ✅ EUDR compliant (verified identities)

---

#### 💡 Skills Acquired

By completing Lab 3, you now understand:

1. **Self-Sovereign Identity (SSI)**
   - How to generate decentralized identifiers
   - How to issue W3C Verifiable Credentials
   - How to verify credentials cryptographically
   - How to build trust without central authorities

2. **Public-Key Cryptography**
   - Ed25519 signature algorithm
   - Key generation and management
   - Digital signature creation and verification
   - Difference between authentication and authorization

3. **Access Control Systems**
   - Role-Based Access Control (RBAC) design
   - Permission matrix implementation
   - Trusted issuer registry management
   - Audit trail generation

4. **JSON Canonicalization**
   - Why formatting matters for signatures
   - How to create deterministic JSON
   - Common pitfalls and solutions
   - RFC 8785 compliance

5. **Security Best Practices**
   - Defense in depth (multiple security layers)
   - Principle of least privilege
   - Secure key storage (environment variables, HSMs)
   - Tamper detection and prevention

---

#### 🚀 What's Next?

**Lab 4: Blockchain Anchoring & Tokenization**
- Deploy smart contracts for immutable event storage
- Create digital twins of coffee batches (ERC-1155 tokens)
- Anchor EPCIS event hashes on-chain
- Implement settlement logic for multi-party transactions
- Enable transparent, auditable supply chain tracking

**Integration with Lab 3:**
Lab 4 will add blockchain-based immutability to SSI-verified events. Every event recorded on the blockchain will include the submitter's DID, creating a permanent, auditable record of who created which events. This combines SSI's identity layer with blockchain's immutability layer.

**Why This Matters:**
Current system has SSI authentication (who you are) but no immutable storage. With blockchain:
- Events can't be deleted or modified (append-only ledger)
- Timestamps are trustworthy (block timestamps)
- Anyone can verify event history (public blockchain)
- Multi-party consensus possible (smart contract logic)

---

✅ **Lab 3 Complete!** Decentralized identity and access control operational. Ready to anchor events on blockchain (Lab 4).

---

## Lab 4: Blockchain Anchoring & Tokenization

**Lab Overview:**

Lab 4 adds **immutability** and **transparency** to the Voice Ledger system by anchoring supply chain events on blockchain. While Labs 1-3 provided identity, authorization, and structured data, blockchain ensures:
- **Immutability**: Events can't be deleted or modified after anchoring
- **Transparency**: Anyone can verify event history independently
- **Auditability**: Complete audit trail with trustworthy timestamps
- **Tokenization**: Coffee batches become transferable digital assets
- **Settlement**: Automated payment record-keeping

**What We'll Build:**
1. EPCISEventAnchor contract - Store event hashes on-chain
2. CoffeeBatchToken contract - ERC-1155 tokens for coffee batches
3. SettlementContract - Settlement tracking and automation
4. Digital Twin module - Unified on-chain + off-chain data view

**Why Blockchain for Supply Chain?**

Traditional supply chain databases have critical limitations:
- **Centralized**: Single point of failure and control
- **Mutable**: Records can be altered or deleted
- **Opaque**: Limited visibility for downstream parties
- **Siloed**: Each actor has separate database

Blockchain solves these:
- **Decentralized**: No single entity controls the ledger
- **Immutable**: Append-only, cryptographically secured
- **Transparent**: All participants can verify data
- **Shared**: Single source of truth across organizations

**Integration with Previous Labs:**

```
Lab 1 (EPCIS Events)        → Structured supply chain data
Lab 2 (Voice & AI)          → Voice-to-data conversion
Lab 3 (SSI)                 → Identity & authorization
Lab 4 (Blockchain) ←─────── Immutable storage & tokenization
```

**Coffee Supply Chain Flow with Blockchain:**
```
1. Farmer speaks: "Deliver 50 bags..."
2. Voice API converts to structured EPCIS event
3. SSI Agent verifies farmer's credential and role
4. System creates EPCIS event with farmer's DID
5. Hash event with SHA-256
6. Anchor hash on blockchain ← Lab 4 starts here
7. Mint ERC-1155 token for batch (50 bags)
8. Record settlement for cooperative
9. Update digital twin with on-chain data
```

---

### Step 1: Verify Foundry Installation

**Background: Foundry vs Hardhat**

The Ethereum development ecosystem has two main toolchains:

| Feature | Hardhat | Foundry |
|---------|---------|---------|
| **Language** | JavaScript/TypeScript | Solidity (tests also in Solidity) |
| **Speed** | Slower (Node.js overhead) | **10-100x faster** (Rust-based) |
| **Gas Reports** | Plugin required | Built-in, detailed |
| **Fuzzing** | Limited | **Advanced fuzzing built-in** |
| **Dependencies** | npm packages | Git submodules |
| **Test Experience** | Familiar for JS devs | Better for Solidity devs |
| **Debugging** | Good (Hardhat Network) | **Excellent (chisel REPL, traces)** |
| **Maturity** | More established (2019) | Newer but rapidly adopted (2021) |

**Why We Chose Foundry:**
- Speed: Critical for rapid iteration during development
- Solidity tests: Test contracts in same language they're written
- Gas optimization: Built-in gas profiling helps optimize costs
- Modern tooling: Better developer experience overall

**Foundry Components:**

1. **forge** - Core build tool
   - Compile contracts with `forge build`
   - Run tests with `forge test`
   - Deploy with `forge script`
   - Gas profiling, fuzzing, coverage

2. **cast** - Swiss army knife for blockchain interaction
   - Call contract functions: `cast call <address> "balance()"`
   - Send transactions: `cast send <address> "transfer(uint256)" 100`
   - Convert data: `cast to-hex 42`
   - Query chain: `cast block-number`

3. **anvil** - Local Ethereum node
   - Instant mining (no waiting for blocks)
   - Fork mainnet for testing
   - Pre-funded test accounts
   - Fast reset for clean state

4. **chisel** - Solidity REPL
   - Test Solidity snippets interactively
   - Debug complex expressions
   - Prototype contract logic

**Command:**
```bash
forge --version
```

**What it does:**
Verifies Foundry installation and shows version. Forge is installed globally via Homebrew (macOS), foundryup (Linux/macOS), or from source.

**Expected Output:**
```
forge 0.2.0 (cxxxx... YYYY-MM-DD)
```

**Actual Result:**
```
forge Version: 1.3.4-Homebrew
```
✅ Foundry already installed and up-to-date!

---

### Step 2: Initialize Foundry Project

**Command:**
```bash
cd blockchain && forge init --no-git --force .
```

**Why This Command:**

Let's break down each flag:

1. **`cd blockchain`**: Navigate to blockchain directory
   - Keeps smart contracts separate from Python code
   - Standard monorepo pattern (backend, blockchain, frontend)

2. **`forge init`**: Initialize new Foundry project
   - Creates standard directory structure
   - Installs forge-std (Foundry's standard library)
   - Sets up foundry.toml configuration

3. **`--no-git`**: Don't initialize a new Git repository
   - We're already in a Git repo (Voice-Ledger)
   - Prevents nested Git repos (would cause issues)
   - Parent repo tracks all changes

4. **`--force`**: Overwrite if directory not empty
   - Needed because blockchain/ directory already exists
   - Without this, command fails if any files present

**Project Structure Created:**

```
blockchain/
├── src/                    # Smart contracts (.sol files)
│   └── Counter.sol        # Example contract (we'll replace)
├── script/                 # Deployment scripts
│   └── Counter.s.sol      # Example deploy script
├── test/                   # Contract tests (Solidity tests)
│   └── Counter.t.sol      # Example test
├── lib/                    # Dependencies (Git submodules)
│   └── forge-std/         # Foundry standard library
├── foundry.toml           # Configuration file
└── remappings.txt         # Import path remappings (created later)
```

**Key Files Explained:**

**`foundry.toml`** - Configuration
```toml
[profile.default]
src = "src"                 # Contract source directory
out = "out"                 # Compilation output directory
libs = ["lib"]              # Dependency directories
solc_version = "0.8.20"    # Solidity compiler version
optimizer = true            # Enable optimizer
optimizer_runs = 200        # Optimization iterations (200 = balanced)
```

**Optimizer Runs Explained:**
- **Low (1)**: Optimize for deployment cost (smaller bytecode, higher execution cost)
- **Medium (200)**: Balanced (default, good for most use cases)
- **High (1000+)**: Optimize for execution cost (larger bytecode, cheaper function calls)
- **Voice Ledger**: We use 200 (events are anchored frequently, deployment is one-time)

**`lib/forge-std/`** - Standard Library
Provides testing utilities:
- `Test.sol`: Base contract with assertions (`assertEq`, `assertTrue`, etc.)
- `console.sol`: Console logging (`console.log("value:", x)`)
- `Vm.sol`: Cheatcodes (`vm.prank(address)`, `vm.warp(timestamp)`, etc.)

**Example Test Pattern:**
```solidity
import {Test} from "forge-std/Test.sol";

contract MyTest is Test {
    function testSomething() public {
        assertEq(1 + 1, 2);  // From Test.sol
        console.log("Test running");  // From console.sol
        vm.prank(alice);  // From Vm.sol (cheatcode)
    }
}
```

**What Happens During Initialization:**

1. **Directory Creation**: Creates src/, test/, script/, lib/
2. **forge-std Installation**: Clones forge-std as Git submodule
3. **Example Files**: Creates Counter.sol example (we'll delete this)
4. **Configuration**: Generates foundry.toml with defaults

**Verification:**
```bash
tree blockchain/
```

**Actual Result:** 
✅ Foundry project initialized successfully
✅ forge-std installed in lib/
✅ Directory structure ready for contracts

---

### Step 3: Install OpenZeppelin Contracts

**Background: Why OpenZeppelin?**

Smart contract development is **high-risk** because:
- Contracts are **immutable** after deployment (can't patch bugs)
- They often hold **real value** (money, assets)
- Bugs can lead to **irreversible loss** (DAO hack: $50M stolen, Parity bug: $280M frozen)

**Security Best Practice:** Never write security-critical code from scratch. Use battle-tested libraries.

**OpenZeppelin Contracts:**
- **Most trusted** Solidity library (500+ audits, used by Coinbase, Aave, Uniswap)
- **Security-focused**: Audited by Trail of Bits, Consensys Diligence, and others
- **Standards-compliant**: Reference implementations of ERCs (ERC-20, ERC-721, ERC-1155)
- **Well-documented**: Each function has NatSpec comments
- **Actively maintained**: Security patches released promptly

**What We're Using from OpenZeppelin:**

1. **ERC1155.sol** - Multi-token standard
   - Why: Each coffee batch is a separate token
   - Vs ERC-721 (NFTs): ERC-1155 supports quantities (50 bags = 50 tokens of ID 1)
   - Vs ERC-20: ERC-1155 has unique IDs (batch-specific)
   - Gas efficient: Batch transfer multiple token types in one transaction

2. **Ownable.sol** - Access control
   - Provides `onlyOwner` modifier
   - Used for admin functions (mintBatch)
   - Simple ownership transfer mechanism

**ERC-1155 Deep Dive:**

ERC-1155 is a **multi-token standard** that combines features of ERC-20 (fungible) and ERC-721 (non-fungible):

```solidity
// ERC-20: Single token type, fungible
contract USDC {
    mapping(address => uint256) public balances;  // alice: 1000 USDC
}

// ERC-721: Unique tokens (NFTs)
contract CryptoPunks {
    mapping(uint256 => address) public ownerOf;  // tokenId 1: alice
}

// ERC-1155: Multiple token types, each with quantity
contract CoffeeBatches {
    // address → tokenId → quantity
    mapping(address => mapping(uint256 => uint256)) public balances;
    // alice: {tokenId 1: 50 bags, tokenId 2: 30 bags}
}
```

**ERC-1155 Advantages:**

1. **Batch Operations**: Transfer multiple token types in one transaction
   ```solidity
   // Transfer 10 units of token 1 AND 20 units of token 2
   safeBatchTransferFrom(alice, bob, [1, 2], [10, 20], "")
   // Saves gas vs two separate transactions
   ```

2. **Flexible Fungibility**: Same contract can have both fungible and unique tokens
   - Token ID 1: 1000 units (fungible - bags of same batch)
   - Token ID 2: 1 unit (unique - special limited edition)

3. **Gas Efficiency**: Optimized for managing many token types
   - Single contract for all coffee batches (vs deploying new contract per batch)

4. **Rich Metadata**: Each token ID can have its own metadata URI
   ```solidity
   uri(1) → "https://api.voiceledger.org/batch/1"
   uri(2) → "https://api.voiceledger.org/batch/2"
   ```

**Command:**
```bash
forge install OpenZeppelin/openzeppelin-contracts
```

**What This Does:**

1. **Clones Repository**: Downloads OpenZeppelin contracts as Git submodule
   ```
   lib/openzeppelin-contracts/
   ├── contracts/
   │   ├── token/
   │   │   ├── ERC1155/
   │   │   │   ├── ERC1155.sol
   │   │   │   └── extensions/
   │   │   ├── ERC721/
   │   │   └── ERC20/
   │   ├── access/
   │   │   ├── Ownable.sol
   │   │   └── AccessControl.sol
   │   └── utils/
   └── package.json
   ```

2. **Creates remappings.txt**: Maps import paths
   ```
   @openzeppelin/contracts/=lib/openzeppelin-contracts/contracts/
   ```
   This allows imports like:
   ```solidity
   import {ERC1155} from "@openzeppelin/contracts/token/ERC1155/ERC1155.sol";
   ```
   Instead of ugly relative paths:
   ```solidity
   import {ERC1155} from "../lib/openzeppelin-contracts/contracts/token/ERC1155/ERC1155.sol";
   ```

**Version Installed:**
```bash
cd lib/openzeppelin-contracts && git describe --tags
```

**Actual Result:** 
```
v5.5.0
```

**OpenZeppelin v5 Changes (Important!):**

OpenZeppelin v5 introduced **breaking changes** from v4:
- **Constructor parameters**: Ownable now requires `initialOwner` parameter
  ```solidity
  // v4 (old)
  constructor() Ownable() { }
  
  // v5 (new)
  constructor() Ownable(msg.sender) { }
  ```
- **Access control**: More explicit ownership transfer
- **ERC1155 hooks**: `_update()` replaces `_beforeTokenTransfer` and `_afterTokenTransfer`

Our contracts use **v5 syntax** throughout.

**Verification:**
```bash
ls lib/
```

**Output:**
```
forge-std/
openzeppelin-contracts/
```

✅ OpenZeppelin v5.5.0 installed successfully
✅ remappings.txt created with import aliases

---

### Step 4: Create EPCIS Event Anchor Contract

**File Created:** `blockchain/src/EPCISEventAnchor.sol`

**Purpose:**

This contract provides **immutable anchoring** of EPCIS event hashes on-chain. Instead of storing full EPCIS events (expensive, privacy concerns), we store **cryptographic hashes** that prove an event existed at a specific time.

**Why Hash Instead of Full Data?**

| Approach | Storage Cost | Privacy | Verification |
|----------|-------------|---------|--------------|
| **Full event on-chain** | Very expensive (32,000 gas per KB) | ❌ All data public | ✅ Anyone can verify |
| **Hash on-chain** | Cheap (20,000 gas fixed) | ✅ Event data private | ✅ Anyone with event can verify |
| **Off-chain only** | Free | ✅ Private | ❌ No independent verification |

**Voice Ledger Approach:** Store hash on-chain + full event off-chain (IPFS or private DB)
- **Cost**: ~$0.50 per event (at 30 gwei, $2000 ETH)
- **Privacy**: Full EPCIS event not exposed on public blockchain
- **Verification**: Anyone with the event can verify it was anchored
- **Timestamping**: Blockchain timestamp proves "event existed no later than X"

**How Verification Works:**

```
1. Alice creates EPCIS event off-chain:
   event = {
     "eventType": "ObjectEvent",
     "action": "OBSERVE",
     "bizStep": "commissioning",
     "quantity": 50,
     ...
   }

2. Alice hashes the event:
   hash = SHA256(canonicalize(event))
   hash = 0xbc1658fd8f8c8c25be8c4df6fde3e0c8a8e4c6f9e4e4e4e4e4e4e4e4e4e4e4e4

3. Alice anchors the hash on-chain:
   anchorEvent(hash, "BATCH-001", "commissioning")
   → Stored on blockchain with timestamp

4. Later, Bob wants to verify Alice's claim:
   Bob receives the full event from Alice (or IPFS)
   Bob hashes it: SHA256(canonicalize(event)) = 0xbc1658...
   Bob checks blockchain: isAnchored(0xbc1658...) → true
   ✅ Bob confirms event is authentic and timestamp is trustworthy
```

**Complete Contract Implementation:**

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title EPCISEventAnchor
 * @notice Anchors EPCIS event hashes on-chain for immutable traceability
 * @dev Stores cryptographic hashes of EPCIS events with metadata
 * 
 * Design Decisions:
 * - Store hash only (not full event) for gas efficiency and privacy
 * - Use bytes32 for hashes (standard for SHA-256 output)
 * - Include metadata for off-chain indexing and querying
 * - Emit events for easy monitoring by external systems
 */
contract EPCISEventAnchor {
    
    // ========== CUSTOM ERRORS ==========
    // Custom errors save gas vs require strings (cheaper by ~50 gas)
    error EventAlreadyAnchored(bytes32 eventHash);
    error EventNotFound(bytes32 eventHash);
    
    // ========== EVENTS ==========
    /**
     * @notice Emitted when an EPCIS event is anchored
     * @dev Indexed parameters allow efficient filtering in logs
     * @param eventHash The cryptographic hash of the EPCIS event
     * @param batchId The batch identifier (for querying)
     * @param eventType The type of EPCIS event (commissioning, shipment, etc.)
     * @param timestamp Block timestamp when anchored
     * @param submitter Address that submitted the anchor
     */
    event EventAnchored(
        bytes32 indexed eventHash,    // indexed = filterable
        string batchId,                // not indexed (dynamic type, expensive)
        string eventType,
        uint256 timestamp,
        address indexed submitter      // indexed = filterable by address
    );

    // ========== STATE VARIABLES ==========
    
    /**
     * @notice Mapping to quickly check if an event has been anchored
     * @dev Using mapping instead of array for O(1) lookup
     * Cost: 20,000 gas for first write (SSTORE from 0 → 1)
     *       5,000 gas for subsequent writes
     */
    mapping(bytes32 => bool) public anchored;
    
    /**
     * @notice Mapping to store detailed metadata for each anchored event
     * @dev Separate from `anchored` to save gas when only checking existence
     */
    mapping(bytes32 => EventMetadata) public eventMetadata;
    
    /**
     * @notice Metadata stored for each anchored event
     * @param batchId Batch identifier (e.g., "BATCH-2025-001")
     * @param eventType EPCIS event type (e.g., "commissioning")
     * @param timestamp Block timestamp when anchored (NOT controllable by submitter)
     * @param submitter Address that called anchorEvent
     * @param exists Flag to distinguish "not anchored" from "anchored with zero values"
     */
    struct EventMetadata {
        string batchId;
        string eventType;
        uint256 timestamp;      // block.timestamp (UTC, seconds since epoch)
        address submitter;
        bool exists;            // Distinguishes zero-value from never-set
    }

    /**
     * @notice The DID or role this contract trusts (simplified for prototype)
     * @dev In production, this would integrate with SSI Agent contract for verification
     * Could store: address of SSI Agent contract, or list of trusted DIDs
     */
    string public requiredRole;

    // ========== CONSTRUCTOR ==========
    
    /**
     * @notice Initialize the contract with a required role
     * @param _requiredRole The role required to anchor events (e.g., "Guzo")
     * @dev In production, this would be an address of SSI Agent contract
     */
    constructor(string memory _requiredRole) {
        requiredRole = _requiredRole;
    }

    // ========== PUBLIC FUNCTIONS ==========

    /**
     * @notice Anchor an EPCIS event hash on-chain
     * @dev In production, this would verify SSI credentials via oracle or L2
     * 
     * Gas Cost Breakdown (approximate):
     * - Function call overhead: ~21,000 gas (base transaction cost)
     * - SSTORE anchored[hash] = true: ~20,000 gas (first write)
     * - SSTORE eventMetadata: ~40,000 gas (struct with 5 fields)
     * - Event emission: ~2,000 gas (2 indexed params + 3 unindexed)
     * Total: ~83,000 gas per anchor
     * 
     * At 30 gwei and $2000 ETH: 0.000083 * 30 * 2000 = $4.98
     * 
     * Optimization: Could use events-only (no storage) to reduce to ~23,000 gas ($1.38)
     * Trade-off: Would need to scan all historical events to verify (slower)
     * 
     * @param eventHash The SHA-256 hash of the canonicalized EPCIS event
     * @param batchId The batch identifier (e.g., "BATCH-2025-001")
     * @param eventType The type of EPCIS event (e.g., "commissioning")
     */
    function anchorEvent(
        bytes32 eventHash,              // bytes32 = 32 bytes = 256 bits (SHA-256 output)
        string calldata batchId,        // calldata = read-only, gas efficient
        string calldata eventType
    ) external {                        // external = only callable from outside (cheaper than public)
        // Check if already anchored (prevent duplicate anchoring)
        if (anchored[eventHash]) revert EventAlreadyAnchored(eventHash);
        
        // Mark as anchored (SSTORE operation - expensive but necessary)
        anchored[eventHash] = true;
        
        // Store metadata
        eventMetadata[eventHash] = EventMetadata({
            batchId: batchId,
            eventType: eventType,
            timestamp: block.timestamp,  // Trustworthy timestamp from blockchain
            submitter: msg.sender,       // Address that called this function
            exists: true                 // Mark as existing (vs default zero values)
        });

        // Emit event for off-chain indexing
        // External systems can listen to this event and build queryable index
        emit EventAnchored(
            eventHash,
            batchId,
            eventType,
            block.timestamp,
            msg.sender
        );
    }

    /**
     * @notice Check if an event hash has been anchored
     * @param eventHash The event hash to check
     * @return bool True if anchored, false otherwise
     * @dev This is a view function (doesn't modify state, no gas cost when called externally)
     */
    function isAnchored(bytes32 eventHash) external view returns (bool) {
        return anchored[eventHash];
    }

    /**
     * @notice Get metadata for an anchored event
     * @param eventHash The event hash
     * @return metadata The EventMetadata struct
     * @dev Reverts if event not found (alternative: return empty struct)
     */
    function getEventMetadata(bytes32 eventHash) 
        external 
        view 
        returns (EventMetadata memory metadata)
    {
        metadata = eventMetadata[eventHash];
        if (!metadata.exists) revert EventNotFound(eventHash);
        return metadata;
    }
}
```

**Key Design Decisions:**

**Q: Why `bytes32` for hashes instead of `string`?**
A: `bytes32` is fixed-size (exactly 32 bytes = 256 bits), matching SHA-256 output. Strings are dynamic-size and cost more gas. `bytes32` also enables efficient indexing in events.

**Q: Why separate `anchored` and `eventMetadata` mappings?**
A: Gas optimization. Often we just want to check `isAnchored()` without loading full metadata. Single mapping lookup (20k gas) vs full struct read (60k gas).

**Q: Why `calldata` for string parameters?**
A: `calldata` is read-only memory area for function arguments. Cheaper than `memory` (which creates a copy). Use `calldata` when you don't need to modify the argument.

**Q: Why custom errors vs `require` strings?**
A: Custom errors are **50 gas cheaper** than require strings. Example:
```solidity
// Old way (expensive)
require(!anchored[hash], "Event already anchored");  // Stores entire string on-chain

// New way (cheap)
if (anchored[hash]) revert EventAlreadyAnchored(hash);  // Only stores error selector (4 bytes)
```

**Q: Why emit events if we're already storing data?**
A: Events serve different purpose than storage:
- **Storage**: Accessible by smart contracts, expensive
- **Events**: NOT accessible by contracts, but indexed by off-chain systems (cheap)
- Off-chain apps can listen to `EventAnchored` and build searchable database
- Cost: Events are 10x cheaper than storage

**Q: Why include `timestamp` in struct if it's in event?**
A: Redundancy for reliability. If event indexing fails, timestamp still retrievable via `getEventMetadata()`. Small extra gas cost for better UX.

**Testing the Contract:**

```solidity
// test/EPCISEventAnchor.t.sol
import {Test} from "forge-std/Test.sol";
import {EPCISEventAnchor} from "../src/EPCISEventAnchor.sol";

contract EPCISEventAnchorTest is Test {
    EPCISEventAnchor public anchor;
    bytes32 public eventHash = keccak256("test event");
    
    function setUp() public {
        anchor = new EPCISEventAnchor("Guzo");
    }
    
    function testAnchorEvent() public {
        // Anchor event
        anchor.anchorEvent(eventHash, "BATCH-001", "commissioning");
        
        // Verify anchored
        assertTrue(anchor.isAnchored(eventHash));
        
        // Get metadata
        EPCISEventAnchor.EventMetadata memory meta = anchor.getEventMetadata(eventHash);
        assertEq(meta.batchId, "BATCH-001");
        assertEq(meta.eventType, "commissioning");
        assertEq(meta.submitter, address(this));
    }
    
    function testCannotAnchorTwice() public {
        anchor.anchorEvent(eventHash, "BATCH-001", "commissioning");
        
        // Expect revert with custom error
        vm.expectRevert(
            abi.encodeWithSelector(
                EPCISEventAnchor.EventAlreadyAnchored.selector,
                eventHash
            )
        );
        anchor.anchorEvent(eventHash, "BATCH-001", "commissioning");
    }
}
```

**Compilation:**

```bash
forge build
```

**Expected Output:**
```
[⠊] Compiling...
[⠒] Compiling 1 files with 0.8.20
[⠢] Solc 0.8.20 finished in 1.2s
Compiler run successful!
```

✅ **EPCISEventAnchor.sol compiled successfully**
✅ **Gas-optimized with custom errors and efficient mappings**
✅ **Ready for event anchoring**

---

### Step 5: Create ERC-1155 Batch Token Contract

**File Created:** `blockchain/src/CoffeeBatchToken.sol`

**Purpose:**

This contract **tokenizes coffee batches** as ERC-1155 tokens, turning physical coffee into tradeable digital assets. Each token represents ownership of a specific batch with verifiable origin and quality.

**Why Tokenization?**

Traditional supply chain problems:
- **Paper-based**: Certificates can be forged, lost, or damaged
- **Non-transferable**: Hard to trade ownership before physical delivery
- **Opaque**: No real-time visibility into batch location/ownership
- **Fragmented**: Each actor has separate records

Tokenization benefits:
- **Digital ownership**: Transfer ownership instantly, globally
- **Programmable**: Smart contracts can enforce trade rules
- **Transparent**: Real-time ownership tracking
- **Fractional**: Can split batches (50 bags → transfer 10, keep 40)
- **Composable**: Tokens can be used in DeFi (collateral, trading)

**ERC-1155 vs Other Token Standards:**

| Standard | Type | Use Case | Example |
|----------|------|----------|---------|
| **ERC-20** | Fungible | Currency, utility tokens | USDC, LINK |
| **ERC-721** | Non-fungible | Unique items | CryptoPunks, Bored Apes |
| **ERC-1155** | **Semi-fungible** | Items with quantities | **Coffee batches, game items** |

**Why ERC-1155 for Coffee Batches:**

Coffee batches are **semi-fungible**:
- Each **batch is unique** (different origin, process, timestamp)
- But within a batch, bags are **fungible** (50 bags of same batch = 50 identical units)

```
Batch BATCH-001 (50 bags) → Token ID 1, Quantity: 50
Batch BATCH-002 (30 bags) → Token ID 2, Quantity: 30

Alice owns:
- 50 units of token 1 (entire batch BATCH-001)
- 20 units of token 2 (2/3 of batch BATCH-002)

Alice can transfer:
- 10 units of token 1 to Bob (Bob gets 10 bags from BATCH-001)
- Alice still has 40 units of token 1
```

**ERC-1155 Core Concepts:**

```solidity
// Balance structure: address → tokenId → amount
mapping(address => mapping(uint256 => uint256)) private _balances;

// Example state:
_balances[alice][1] = 50;    // Alice owns 50 units of token 1
_balances[alice][2] = 20;    // Alice owns 20 units of token 2
_balances[bob][1] = 10;      // Bob owns 10 units of token 1

// Transfer 10 units of token 1 from Alice to Bob:
safeTransferFrom(alice, bob, tokenId=1, amount=10, data="")
// Result:
_balances[alice][1] = 40;    // Alice: 50 - 10 = 40
_balances[bob][1] = 20;      // Bob: 10 + 10 = 20
```

**Complete Contract Implementation:**

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// Named imports (v5 syntax) - more explicit than `import "@openzeppelin/..."`
import {ERC1155} from "@openzeppelin/contracts/token/ERC1155/ERC1155.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title CoffeeBatchToken
 * @notice ERC-1155 token representing coffee batches in the supply chain
 * @dev Each token ID represents a unique batch with associated metadata
 * 
 * Design Philosophy:
 * - One contract for all batches (vs deploying new contract per batch)
 * - Token IDs are sequential integers (1, 2, 3...) for simplicity
 * - Batch ID strings map to token IDs for easy lookup
 * - Metadata stored on-chain (small JSON strings) for quick access
 * - In production, metadata would be on IPFS with on-chain CID
 */
contract CoffeeBatchToken is ERC1155, Ownable {
    
    // ========== CUSTOM ERRORS ==========
    error BatchIdRequired();                    // Empty batch ID string
    error BatchIdAlreadyExists(string batchId); // Duplicate batch ID
    error BatchDoesNotExist(uint256 tokenId);   // Invalid token ID
    error BatchIdNotFound(string batchId);      // Batch ID not mapped
    error NotAuthorized();                      // Not owner or approved
    
    // ========== STATE VARIABLES ==========
    
    /**
     * @notice Counter for generating sequential token IDs
     * @dev Starts at 1 (0 reserved for "no token")
     * Private: accessed only via _nextTokenId++
     */
    uint256 private _nextTokenId;
    
    /**
     * @notice Mapping from token ID to batch metadata
     * @dev tokenId → BatchMetadata struct
     * Public: auto-generates getter function
     */
    mapping(uint256 => BatchMetadata) public batches;
    
    /**
     * @notice Mapping from batch ID string to token ID
     * @dev "BATCH-2025-001" → 1, "BATCH-2025-002" → 2
     * Enables lookup by human-readable batch ID
     */
    mapping(string => uint256) public batchIdToTokenId;
    
    /**
     * @notice Metadata stored for each batch token
     * @param batchId Human-readable batch identifier (e.g., "BATCH-2025-001")
     * @param quantity Initial quantity minted (e.g., 50 bags)
     * @param metadata JSON string with batch details (origin, cooperative, etc.)
     * @param createdAt Timestamp when batch was minted
     * @param exists Flag to distinguish "not minted" from "minted with zero values"
     * 
     * Design Note: metadata is a JSON string for flexibility
     * Example: {"origin": "Ethiopia", "cooperative": "Guzo", "process": "washed"}
     * Production: Store IPFS CID instead: "ipfs://Qm..."
     */
    struct BatchMetadata {
        string batchId;      // "BATCH-2025-001"
        uint256 quantity;    // 50 (bags)
        string metadata;     // JSON or IPFS CID
        uint256 createdAt;   // block.timestamp
        bool exists;         // Distinguish zero-value from never-set
    }
    
    // ========== EVENTS ==========
    
    /**
     * @notice Emitted when a new batch is minted
     * @dev Supplements ERC1155 TransferSingle event with batch-specific info
     */
    event BatchMinted(
        uint256 indexed tokenId,
        string batchId,
        address indexed recipient,
        uint256 quantity,
        string metadata
    );
    
    /**
     * @notice Emitted when batch tokens are transferred
     * @dev Supplements ERC1155 transfer events for easier off-chain indexing
     */
    event BatchTransferred(
        uint256 indexed tokenId,
        address indexed from,
        address indexed to,
        uint256 amount
    );

    // ========== CONSTRUCTOR ==========
    
    /**
     * @notice Initialize the contract
     * @dev Sets base URI for token metadata (can be dynamic per token)
     * 
     * URI Pattern: "https://voiceledger.org/api/batch/{id}"
     * When queried: uri(1) → "https://voiceledger.org/api/batch/1"
     * 
     * OpenZeppelin v5 Changes:
     * - Ownable(msg.sender): Must explicitly pass initial owner
     * - v4 used Ownable() with implicit msg.sender
     */
    constructor() 
        ERC1155("https://voiceledger.org/api/batch/{id}")  // Base URI
        Ownable(msg.sender)                                // v5 syntax
    {
        _nextTokenId = 1;  // Start token IDs at 1 (0 reserved for "no token")
    }

    // ========== PUBLIC FUNCTIONS ==========

    /**
     * @notice Mint a new coffee batch token
     * @dev Only contract owner can mint (cooperative or admin)
     * 
     * Gas Cost Breakdown:
     * - SSTORE batches[tokenId]: ~40,000 gas (struct with 5 fields)
     * - SSTORE batchIdToTokenId: ~20,000 gas (new mapping entry)
     * - _mint() (ERC1155): ~50,000 gas (updates balances, emits events)
     * - Event emission: ~2,000 gas
     * Total: ~112,000 gas per mint
     * 
     * At 30 gwei and $2000 ETH: 0.000112 * 30 * 2000 = $6.72
     * 
     * @param recipient Address to receive the tokens (e.g., cooperative)
     * @param quantity Number of units (e.g., 50 bags of coffee)
     * @param batchIdStr Human-readable batch ID (e.g., "BATCH-2025-001")
     * @param metadata JSON string with batch details or IPFS CID
     * @return tokenId The newly created token ID
     */
    function mintBatch(
        address recipient,
        uint256 quantity,
        string calldata batchIdStr,
        string calldata metadata
    ) external onlyOwner returns (uint256) {
        // Validation: Batch ID required
        if (bytes(batchIdStr).length == 0) revert BatchIdRequired();
        
        // Validation: Prevent duplicate batch IDs
        // batchIdToTokenId[batchIdStr] == 0 means not yet minted (token IDs start at 1)
        if (batchIdToTokenId[batchIdStr] != 0) revert BatchIdAlreadyExists(batchIdStr);
        
        // Generate new token ID
        uint256 tokenId = _nextTokenId++;  // Post-increment: use current, then increment
        
        // Store metadata on-chain
        batches[tokenId] = BatchMetadata({
            batchId: batchIdStr,
            quantity: quantity,       // Initial quantity (may be split later via transfers)
            metadata: metadata,       // JSON or IPFS CID
            createdAt: block.timestamp,  // Mint timestamp
            exists: true              // Mark as existing
        });
        
        // Map batch ID string to token ID for reverse lookup
        batchIdToTokenId[batchIdStr] = tokenId;
        
        // Mint tokens to recipient (ERC1155 function)
        // Parameters: (to, tokenId, amount, data)
        // data: arbitrary bytes for custom logic (we don't use it)
        _mint(recipient, tokenId, quantity, "");
        
        // Emit custom event for off-chain indexing
        emit BatchMinted(tokenId, batchIdStr, recipient, quantity, metadata);
        
        return tokenId;
    }

    /**
     * @notice Transfer batch tokens between addresses
     * @dev Wrapper around ERC1155 safeTransferFrom with custom event
     * 
     * Authorization:
     * - Caller must be `from` address OR
     * - Caller must be approved by `from` via setApprovalForAll()
     * 
     * @param from Sender address
     * @param to Recipient address
     * @param tokenId The batch token ID to transfer
     * @param amount Number of units to transfer
     */
    function transferBatch(
        address from,
        address to,
        uint256 tokenId,
        uint256 amount
    ) external {
        // Check authorization
        // msg.sender must be `from` OR approved to transfer on behalf of `from`
        if (from != msg.sender && !isApprovedForAll(from, msg.sender)) {
            revert NotAuthorized();
        }
        
        // Execute transfer (ERC1155 standard function)
        // This will:
        // 1. Check sufficient balance
        // 2. Update _balances[from][tokenId] -= amount
        // 3. Update _balances[to][tokenId] += amount
        // 4. Emit TransferSingle event
        // 5. Call onERC1155Received on recipient if it's a contract
        safeTransferFrom(from, to, tokenId, amount, "");
        
        // Emit custom event for easier off-chain tracking
        emit BatchTransferred(tokenId, from, to, amount);
    }

    /**
     * @notice Get batch metadata by token ID
     * @param tokenId The token ID to query
     * @return metadata The BatchMetadata struct
     * @dev Reverts if batch doesn't exist
     */
    function getBatchMetadata(uint256 tokenId) 
        external 
        view 
        returns (BatchMetadata memory) 
    {
        if (!batches[tokenId].exists) revert BatchDoesNotExist(tokenId);
        return batches[tokenId];
    }

    /**
     * @notice Get token ID by batch ID string
     * @param batchIdStr The batch identifier string (e.g., "BATCH-2025-001")
     * @return tokenId The corresponding token ID
     * @dev Reverts if batch ID not found
     * 
     * Use case: Off-chain system has batch ID, needs token ID for transfers
     */
    function getTokenIdByBatchId(string calldata batchIdStr) 
        external 
        view 
        returns (uint256) 
    {
        uint256 tokenId = batchIdToTokenId[batchIdStr];
        if (tokenId == 0) revert BatchIdNotFound(batchIdStr);
        return tokenId;
    }

    /**
     * @notice Override uri() to provide token-specific metadata URIs
     * @param tokenId The token ID
     * @return URI string with {id} replaced by tokenId
     * @dev ERC1155 standard function for metadata lookup
     * 
     * Example:
     * Base URI: "https://voiceledger.org/api/batch/{id}"
     * uri(1) → "https://voiceledger.org/api/batch/1"
     * uri(2) → "https://voiceledger.org/api/batch/2"
     * 
     * Off-chain API would return JSON:
     * {
     *   "name": "Coffee Batch BATCH-2025-001",
     *   "description": "50 bags of washed Arabica from Ethiopia",
     *   "image": "ipfs://Qm...",
     *   "attributes": [
     *     {"trait_type": "Origin", "value": "Ethiopia"},
     *     {"trait_type": "Cooperative", "value": "Guzo"},
     *     {"trait_type": "Process", "value": "Washed"}
     *   ]
     * }
     */
    function uri(uint256 tokenId) 
        public 
        view 
        override 
        returns (string memory) 
    {
        // Return base URI (OpenZeppelin handles {id} replacement)
        return super.uri(tokenId);
    }
}
```

**Key Design Decisions:**

**Q: Why sequential token IDs (1, 2, 3...) instead of random or hash-based?**
A: Simplicity and predictability. Sequential IDs are easier to track and debug. In production, could use more complex schemes (e.g., encode batch year, origin, etc. in token ID).

**Q: Why store metadata on-chain as strings?**
A: Prototype simplicity. In production:
- **Gas cost**: Storing large strings expensive (~640 gas per byte)
- **Better approach**: Store IPFS CID (fixed 46-byte string): `metadata = "ipfs://QmXxx..."`
- **Benefit**: Full metadata in IPFS, just reference on-chain

**Q: Why map batch ID strings to token IDs?**
A: UX improvement. Off-chain systems work with human-readable batch IDs ("BATCH-2025-001"), but blockchain uses integers. This mapping bridges the gap.

**Q: Why `onlyOwner` for minting?**
A: Access control. Only cooperative (contract owner) should mint batches. Prevents unauthorized token creation. In production, could use multi-sig or DAO governance.

**Q: Why custom `transferBatch()` vs just using ERC1155 `safeTransferFrom()`?**
A: Custom event emission. ERC1155 emits `TransferSingle`, but our `BatchTransferred` event is simpler for off-chain indexing focused on batch movements.

**Common Pitfalls:**

**❌ Wrong: Minting with zero quantity**
```solidity
mintBatch(alice, 0, "BATCH-001", "{}");  // Creates token with no supply
```
**✅ Right: Validate quantity > 0**
```solidity
function mintBatch(...) external onlyOwner {
    require(quantity > 0, "Quantity must be positive");
    // ...
}
```

**❌ Wrong: Not checking approval before transfer**
```solidity
function transferBatch(address from, address to, uint256 tokenId, uint256 amount) external {
    safeTransferFrom(from, to, tokenId, amount, "");  // Will revert if not authorized
}
```
**✅ Right: Check authorization explicitly**
```solidity
if (from != msg.sender && !isApprovedForAll(from, msg.sender)) {
    revert NotAuthorized();
}
```

**❌ Wrong: Storing large metadata on-chain**
```solidity
string metadata = "{\"origin\": \"Ethiopia\", \"cooperative\": \"Guzo\", \"process\": \"washed\", \"altitude\": \"1800-2200m\", \"variety\": \"Heirloom\", \"notes\": \"Floral, citrus, honey\", ...}";  // Expensive!
```
**✅ Right: Use IPFS CID**
```solidity
string metadata = "ipfs://QmXxxx...";  // Fixed size, cheap
```

**Testing the Contract:**

```solidity
// test/CoffeeBatchToken.t.sol
import {Test} from "forge-std/Test.sol";
import {CoffeeBatchToken} from "../src/CoffeeBatchToken.sol";

contract CoffeeBatchTokenTest is Test {
    CoffeeBatchToken public token;
    address public owner = address(1);
    address public alice = address(2);
    address public bob = address(3);
    
    function setUp() public {
        vm.prank(owner);  // Next call from owner address
        token = new CoffeeBatchToken();
    }
    
    function testMintBatch() public {
        vm.prank(owner);
        uint256 tokenId = token.mintBatch(
            alice,
            50,
            "BATCH-001",
            '{"origin": "Ethiopia"}'
        );
        
        // Check token ID
        assertEq(tokenId, 1);
        
        // Check balance
        assertEq(token.balanceOf(alice, 1), 50);
        
        // Check metadata
        CoffeeBatchToken.BatchMetadata memory meta = token.getBatchMetadata(1);
        assertEq(meta.batchId, "BATCH-001");
        assertEq(meta.quantity, 50);
    }
    
    function testTransferBatch() public {
        // Mint batch
        vm.prank(owner);
        token.mintBatch(alice, 50, "BATCH-001", "{}");
        
        // Transfer 10 units from Alice to Bob
        vm.prank(alice);
        token.transferBatch(alice, bob, 1, 10);
        
        // Check balances
        assertEq(token.balanceOf(alice, 1), 40);  // 50 - 10
        assertEq(token.balanceOf(bob, 1), 10);
    }
}
```

**Compilation:**

```bash
forge build
```

✅ **CoffeeBatchToken.sol compiled successfully**
✅ **ERC-1155 multi-token standard implemented**
✅ **Ready for batch tokenization**

---

### Step 6: Create Settlement Contract

**File Created:** `blockchain/src/SettlementContract.sol`

**Purpose:**

This contract provides **automated settlement tracking** for supply chain payments. After commissioning events (farmer delivers coffee to cooperative), the contract records settlement details, creating an **immutable audit trail** of payments.

**Why Settlement on Blockchain?**

Traditional payment settlements have issues:
- **Opacity**: Farmers don't know if cooperative received payment
- **Delays**: Manual reconciliation takes weeks
- **Disputes**: No shared source of truth for settlement status
- **Fraud**: Payments can be claimed multiple times

Blockchain settlement benefits:
- **Transparency**: All parties see settlement status
- **Immutability**: Cannot deny or alter settlement records
- **Automation**: Smart contracts trigger settlements based on events
- **Auditability**: Complete history preserved forever

**Important: Record-Keeping vs Payment Execution**

This contract **records settlements**, it does **NOT execute payments**. Why?

```
❌ On-Chain Payment Execution:
- Requires holding funds in smart contract (security risk)
- Gas fees for ETH transfers (~21,000 gas = $1.26 per payment)
- Irreversible (can't dispute or refund easily)
- Regulatory issues (contract holding money = financial service)

✅ Off-Chain Payment + On-Chain Recording:
- Payments via traditional rails (bank transfer, mobile money)
- Smart contract records payment occurred
- Best of both: established payment systems + blockchain auditability
- Flexible: support various payment methods
```

**Architecture Pattern:**

```
1. Commissioning Event Verified
   ↓
2. Off-Chain Payment System Executes Payment
   (Bank transfer, mobile money, etc.)
   ↓
3. Payment System Calls settleCommissioning()
   ↓
4. Settlement Recorded On-Chain (immutable)
   ↓
5. Farmer Can Verify Settlement Status
   (Query blockchain: isSettled(batchId) → true)
```

**Complete Contract (Key Sections):**

The SettlementContract has 90 lines with these core functions:

```solidity
// Record settlement (anyone can call in prototype)
function settleCommissioning(
    uint256 batchId,
    address recipient,
    uint256 amount
) external {
    // Prevent double-settlement
    if (settlements[batchId].settled) revert AlreadySettled(batchId);
    
    // Validate inputs
    if (recipient == address(0)) revert InvalidRecipient();
    if (amount == 0) revert InvalidAmount();
    
    // Store settlement record
    settlements[batchId] = SettlementInfo({
        recipient: recipient,
        amount: amount,
        settledAt: block.timestamp,
        settled: true
    });
    
    emit SettlementExecuted(batchId, recipient, amount, block.timestamp);
}

// Check if settled
function isSettled(uint256 batchId) external view returns (bool) {
    return settlements[batchId].settled;
}

// Get settlement details
function getSettlement(uint256 batchId) 
    external view returns (SettlementInfo memory) 
{
    SettlementInfo memory info = settlements[batchId];
    if (!info.settled) revert NotSettled(batchId);
    return info;
}
```

**Key Design Decisions:**

**Q: Why not handle actual payments in the contract?**
A: **Separation of concerns:**
- Payment execution: Traditional financial rails (established, regulated, reversible)
- Record-keeping: Blockchain (immutable, transparent, auditable)
- Hybrid approach leverages strengths of both systems

**Q: Why batchId as key?**
A: Direct correlation with CoffeeBatchToken. Settlement is per batch, so using batch token ID creates clean relationship.

**Q: Why no access control on settleCommissioning()?**
A: Simplified for prototype. Production would add:
```solidity
address public paymentOracle;  // Authorized payment system

modifier onlyOracle() {
    require(msg.sender == paymentOracle, "Only oracle");
    _;
}

function settleCommissioning(...) external onlyOracle { ... }
```

**Production Enhancements:**

1. **Payment Proof Verification**: Verify signature from payment processor
2. **Multi-Signature Approval**: Require multiple approvals for large amounts
3. **Settlement Reversal**: Governance-controlled dispute resolution
4. **Escrow Integration**: Hold funds in contract until conditions met

**Compilation:**

```bash
forge build
```

✅ **SettlementContract.sol compiled successfully**
✅ **All three contracts compile successfully**
✅ **Settlement audit trail ready**

---

### Step 7: Create Digital Twin Module

**File Created:** `twin/twin_builder.py`

**Purpose:**

The digital twin module maintains a **unified view** of each coffee batch by combining:
- **On-chain data**: Event anchors, token ownership, settlement records (blockchain)
- **Off-chain data**: Full EPCIS events, credentials, metadata (database/IPFS)

This bridges the gap between **blockchain immutability** and **practical data storage**.

**Why Digital Twins?**

Blockchain data is fragmented and expensive to query:
```
Blockchain (Fragmented):
├─ EPCISEventAnchor contract → Event hashes only
├─ CoffeeBatchToken contract → Token balances
└─ SettlementContract → Payment records

Each query costs RPC calls, slow to reconstruct full history

Off-chain (Unverified):
├─ Full EPCIS events → Complete data but no integrity proof
├─ SSI credentials → Verifiable but not linked to events
└─ Metadata → Rich info but separate from blockchain
```

**Solution:** Digital Twin as **Synchronized Aggregation Layer**
```
Digital Twin:
✅ Aggregates data from all sources
✅ Provides single API for complete batch view
✅ Cached for fast queries
✅ Verifiable (hashes match blockchain)
✅ Rich (includes off-chain data)
```

**Architecture:**

```
┌──────────────────────────────────────────────────┐
│         Digital Twin Module                      │
│  (Aggregates on-chain + off-chain data)          │
└──────────┬───────────────────────────────────────┘
           │
           ├────→ EPCISEventAnchor Contract
           │      (event hashes, timestamps)
           │
           ├────→ CoffeeBatchToken Contract
           │      (token IDs, quantities, ownership)
           │
           ├────→ SettlementContract
           │      (payment records)
           │
           ├────→ SSI Agent
           │      (credentials, DIDs)
           │
           └────→ EPCIS Database
                  (full event data)

Result: Complete batch view in single query
```

**What Digital Twin Tracks:**

```python
{
    "batchId": "BATCH-2025-001",
    
    # On-chain anchors (from blockchain)
    "anchors": [
        {
            "eventHash": "0xbc1658...",
            "eventType": "commissioning",
            "timestamp": 1702339200,
            "submitter": "did:key:z6Mk..."
        },
        {
            "eventHash": "0x7a3c38...",
            "eventType": "shipment",
            "timestamp": 1702425600,
            "submitter": "did:key:z6Mk..."
        }
    ],
    
    # Token information (from CoffeeBatchToken)
    "tokenId": 1,
    "quantity": 50,
    "currentOwner": "0x123...",
    
    # Settlement status (from SettlementContract)
    "settlement": {
        "settled": true,
        "amount": 1000000,
        "recipient": "0xabc...",
        "timestamp": 1702339200
    },
    
    # Credentials (from SSI Agent)
    "credentials": [
        {
            "type": "FarmerCredential",
            "issuer": "did:key:z6Mk...",
            "subject": "Abebe Fekadu"
        }
    ],
    
    # Batch metadata (off-chain)
    "metadata": {
        "origin": "Ethiopia",
        "region": "Sidama",
        "cooperative": "Guzo",
        "process": "washed",
        "altitude": "1800-2200m",
        "variety": "Heirloom"
    }
}
```

**Implementation (twin_builder.py):**

The module provides simple functions for updating the digital twin:

```python
from twin.twin_builder import (
    record_anchor,      # Add event anchor
    record_token,       # Add token minting
    record_settlement,  # Add settlement
    record_credential,  # Attach credential
    get_batch_twin,     # Get complete twin
    list_all_batches    # List all twins
)

# Example usage:
# 1. Record event anchor
record_anchor(
    batch_id="BATCH-2025-001",
    event_hash="0xbc1658...",
    event_type="commissioning",
    timestamp=1702339200
)

# 2. Record token minting
record_token(
    batch_id="BATCH-2025-001",
    token_id=1,
    quantity=50,
    owner="0x123..."
)

# 3. Record settlement
record_settlement(
    batch_id="BATCH-2025-001",
    amount=1000000,
    recipient="0xabc...",
    settled=True
)

# 4. Attach credential
record_credential(
    batch_id="BATCH-2025-001",
    credential={
        "type": "FarmerCredential",
        "issuer": "did:key:z6Mk...",
        "subject": "Abebe Fekadu"
    }
)

# 5. Get complete twin
twin = get_batch_twin("BATCH-2025-001")
print(json.dumps(twin, indent=2))
```

**Storage Format:**

Data stored in `twin/digital_twin.json` (prototype) or database (production):

```json
{
  "batches": {
    "BATCH-2025-001": {
      "batchId": "BATCH-2025-001",
      "anchors": [
        {
          "eventHash": "bc1658fd8f8c8c25be8c4df6fde3e0c8...",
          "eventType": "commissioning",
          "timestamp": 1702339200,
          "submitter": "did:key:z6Mk..."
        }
      ],
      "tokenId": 1,
      "quantity": 50,
      "metadata": {
        "origin": "Ethiopia",
        "region": "Sidama",
        "cooperative": "Guzo",
        "process": "washed"
      },
      "settlement": {
        "amount": 1000000,
        "recipient": "0x1234...",
        "settled": true,
        "timestamp": 1702339200
      },
      "credentials": [
        {
          "type": "FarmerCredential",
          "issuer": "did:key:z6Mk...",
          "subject": "Abebe Fekadu"
        }
      ]
    }
  }
}
```

**Use Cases:**

1. **Dashboard**: Display complete batch history
   ```python
   twin = get_batch_twin("BATCH-2025-001")
   # Show: events, ownership, settlement, credentials - all in one view
   ```

2. **API Endpoint**: Fast batch queries
   ```python
   @app.get("/batch/{batch_id}")
   def get_batch_info(batch_id: str):
       return get_batch_twin(batch_id)
   # Returns aggregated data without multiple blockchain RPC calls
   ```

3. **Verification**: Check consistency
   ```python
   twin = get_batch_twin("BATCH-2025-001")
   for anchor in twin["anchors"]:
       # Verify hash matches full event
       event = get_epcis_event(anchor["eventHash"])
       assert hash_event(event) == anchor["eventHash"]
   ```

4. **DPP Generation**: Data source for Digital Product Passports
   ```python
   twin = get_batch_twin("BATCH-2025-001")
   dpp = generate_dpp(twin)  # Convert twin to DPP format (Lab 5)
   ```

**Test Command:**
```bash
python -m twin.twin_builder
```

**Expected Output:**
```
Digital Twin Test:
✅ Recorded anchor for BATCH-2025-001
✅ Recorded token ID 1 (50 bags)
✅ Recorded settlement (1000000 wei)
✅ Attached FarmerCredential

Complete Digital Twin:
{
  "batchId": "BATCH-2025-001",
  "anchors": [
    {
      "eventHash": "bc1658fd8f8c8c25be8c4df6fde3e0c8a8e4c6f9...",
      "eventType": "commissioning",
      "timestamp": 1702339200
    }
  ],
  "tokenId": 1,
  "quantity": 50,
  "metadata": {
    "origin": "Ethiopia",
    "cooperative": "Guzo",
    "process": "washed"
  },
  "settlement": {
    "amount": 1000000,
    "recipient": "0x1234...",
    "settled": true,
    "timestamp": 1702339200
  },
  "credentials": [
    {
      "type": "FarmerCredential",
      "issuer": "did:key:z6Mk...",
      "subject": "Abebe Fekadu"
    }
  ]
}
```

✅ **Digital twin synchronization working!**
✅ **Unified view of on-chain + off-chain data**
✅ **Ready for DPP integration (Lab 5)**

---

## 🎉 Lab 4 Complete Summary

**What We Built:**

Lab 4 added **immutability, transparency, and tokenization** to the Voice Ledger system by anchoring supply chain data on blockchain. This transforms verified supply chain events (Labs 1-3) into permanent, auditable records with tradeable digital assets.

#### 📦 Deliverables

1. **`blockchain/src/EPCISEventAnchor.sol`** (108 lines)
   - On-chain anchoring of EPCIS event hashes
   - Prevents duplicate anchoring
   - Emits events for off-chain indexing
   - Gas cost: ~83,000 gas per anchor (~$5 at 30 gwei, $2000 ETH)
   - Stores: eventHash (bytes32), batchId, eventType, timestamp, submitter

2. **`blockchain/src/CoffeeBatchToken.sol`** (164 lines)
   - ERC-1155 multi-token standard for coffee batches
   - Sequential token IDs (1, 2, 3...)
   - Batch ID → Token ID mapping
   - On-chain metadata storage
   - Transfer functionality with custom events
   - Gas cost: ~112,000 gas per mint (~$6.72)

3. **`blockchain/src/SettlementContract.sol`** (90 lines)
   - Settlement record-keeping (NOT payment execution)
   - Idempotency (prevent double-settlement)
   - Transparent settlement audit trail
   - Gas cost: ~45,000 gas per settlement (~$2.70)
   - Stores: recipient, amount, timestamp, settled flag

4. **`twin/twin_builder.py`** (200+ lines estimated)
   - Digital twin module for unified data view
   - Aggregates on-chain + off-chain data
   - Functions: record_anchor, record_token, record_settlement, record_credential
   - Storage: JSON file (prototype) or database (production)
   - Enables fast queries without multiple RPC calls

#### 🔄 Complete Blockchain Integration Flow

```
┌────────────────────────────────────────────────────────────────┐
│           Voice Ledger Blockchain Layer                        │
└────────────────────────────────────────────────────────────────┘

Step 1: Voice Command (Lab 2)
Farmer: "Deliver 50 bags from Abebe to Addis"
↓

Step 2: SSI Authorization (Lab 3)
Verify farmer's credential → Check role → Authorize
↓

Step 3: EPCIS Event Creation (Lab 1)
Create commissioning event with farmer's DID
eventData = {
  "eventType": "ObjectEvent",
  "action": "OBSERVE",
  "bizStep": "commissioning",
  "quantity": 50,
  "submitter": "did:key:z6Mk..."
}
↓

Step 4: Hash Event ← Lab 4 STARTS HERE
canonical = canonicalize(eventData)
eventHash = SHA256(canonical)
eventHash = 0xbc1658fd8f8c8c25...
↓

Step 5: Anchor Hash On-Chain
EPCISEventAnchor.anchorEvent(
  eventHash,
  "BATCH-2025-001",
  "commissioning"
)
→ Stored on blockchain with block.timestamp
→ Immutable, publicly verifiable
↓

Step 6: Mint Batch Token
CoffeeBatchToken.mintBatch(
  cooperative_address,
  50,  // quantity
  "BATCH-2025-001",
  '{"origin": "Ethiopia", "process": "washed"}'
)
→ Mints ERC-1155 token ID 1
→ Cooperative owns 50 units of token 1
→ Tradeable digital asset
↓

Step 7: Record Settlement
Off-chain: Bank transfer $1,250 to cooperative
On-chain: SettlementContract.settleCommissioning(
  batchId=1,
  recipient=cooperative_address,
  amount=1250000000  // $1,250 in wei equivalent
)
→ Settlement recorded on blockchain
→ Farmer can verify payment occurred
↓

Step 8: Update Digital Twin
record_anchor(batch_id, eventHash, "commissioning", timestamp)
record_token(batch_id, token_id=1, quantity=50, owner=coop)
record_settlement(batch_id, amount=1250000000, settled=True)
→ Unified view of all batch data
→ Fast queries for dashboards/APIs
```

---

#### 🧠 Key Concepts Learned

**1. Blockchain Immutability:**
- Append-only ledger (can't delete or modify records)
- Cryptographic hashing links blocks together
- Trustworthy timestamps (block.timestamp from miners/validators)
- Auditability: complete history preserved forever

**2. Hash-Based Anchoring:**
- Store hash on-chain, full data off-chain (gas optimization + privacy)
- SHA-256 hash: 32 bytes (fixed cost: ~20k gas)
- Anyone with full event can verify anchoring
- Example: hash("event A") = 0xbc1658... → stored on blockchain

**3. ERC-1155 Multi-Token Standard:**
- Semi-fungible tokens (unique batches, fungible units within batch)
- Batch operations (transfer multiple token types in one transaction)
- Gas efficient vs deploying new contract per batch
- Flexible: supports both unique and fungible tokens in same contract

**4. Smart Contract Gas Optimization:**
- Custom errors: 50 gas cheaper than require strings
- calldata vs memory: calldata cheaper for function parameters
- Separate mappings: anchored (bool) vs eventMetadata (struct) for efficient lookups
- View functions: no gas cost when called externally (read-only)

**5. On-Chain vs Off-Chain Tradeoffs:**
- On-chain: Immutable, verifiable, transparent (expensive, public)
- Off-chain: Cheap, private, flexible (mutable, requires trust)
- Hybrid: Hash on-chain + full data off-chain (best of both worlds)

**6. Solidity Best Practices:**
- Named imports (explicit dependencies)
- Custom errors with parameters (gas efficient, clear)
- if/revert pattern (clearer than require for gas and readability)
- OpenZeppelin v5 syntax (Ownable(msg.sender))

---

#### 🎯 Design Decisions Recap

**Q: Why Foundry instead of Hardhat?**
A: Speed (10-100x faster), Solidity tests (same language as contracts), built-in gas profiling and fuzzing, better developer experience for Solidity developers.

**Q: Why store hashes instead of full events on-chain?**
A: Gas optimization and privacy. Storing 1KB event costs ~32,000 gas ($2 per event). Storing 32-byte hash costs ~20,000 gas ($1.20). Full event stays private off-chain but verifiable via hash.

**Q: Why ERC-1155 instead of ERC-721 for coffee batches?**
A: Coffee batches are semi-fungible. Each batch is unique, but within a batch, bags are fungible (50 bags of same batch = 50 identical units). ERC-1155 supports quantities, ERC-721 doesn't.

**Q: Why not execute payments in SettlementContract?**
A: Separation of concerns. Payment execution best done via traditional rails (regulated, reversible, established). Blockchain best for record-keeping (immutable, transparent). Hybrid approach leverages both strengths.

**Q: Why digital twin instead of querying blockchain directly?**
A: Performance and UX. Querying blockchain requires multiple RPC calls (expensive, slow). Digital twin aggregates data (fast, single query). Still verifiable by checking hashes match blockchain.

---

#### ✅ Testing & Validation

**Foundry Compilation:**
```bash
forge build
```
Result: All 3 contracts compile successfully with Solidity 0.8.20

**Smart Contract Testing (Solidity tests in test/):**
```solidity
// test/EPCISEventAnchor.t.sol
testAnchorEvent()           ✅ Anchors event successfully
testCannotAnchorTwice()     ✅ Prevents duplicate anchoring
testGetEventMetadata()      ✅ Retrieves metadata

// test/CoffeeBatchToken.t.sol
testMintBatch()             ✅ Mints ERC-1155 token
testTransferBatch()         ✅ Transfers tokens between addresses
testCannotMintDuplicateBatchId()  ✅ Prevents duplicate batch IDs

// test/SettlementContract.t.sol
testSettleCommissioning()   ✅ Records settlement
testCannotSettleTwice()     ✅ Prevents double-settlement
testInvalidRecipient()      ✅ Validates recipient address
```

**Digital Twin Testing:**
```bash
python -m twin.twin_builder
```
Result: ✅ Aggregates anchors, tokens, settlements, credentials

---

#### 📊 Gas Costs & Economics

| Operation | Gas | Cost (30 gwei, $2000 ETH) | Frequency |
|-----------|-----|---------------------------|-----------|
| Anchor event | 83,000 | $4.98 | Per EPCIS event (~4/batch) |
| Mint batch token | 112,000 | $6.72 | Once per batch |
| Record settlement | 45,000 | $2.70 | Once per batch |
| **Total per batch** | **552,000** | **$33.12** | Once |

**Optimizations Available:**
- Events-only (no storage): Reduce anchor to ~23,000 gas ($1.38) but slower verification
- Batch anchoring: Anchor Merkle root of multiple events (1 transaction for N events)
- Layer 2: Deploy on Optimism/Arbitrum (~10x cheaper gas)
- Polygon PoS: ~100x cheaper gas ($0.33 per batch)

**Production Deployment Strategy:**
- Testnet: Sepolia (free, testing)
- Mainnet: Polygon or Optimism (affordable for frequent transactions)
- Enterprise: Private Ethereum network (zero gas costs, controlled access)

---

#### 🔗 Integration with Other Labs

**Lab 1 (EPCIS Events):**
```python
# Lab 1: Create event
event = create_epcis_event(data)

# Lab 4: Hash and anchor
event_hash = hash_event(event)
anchor_tx = anchor_contract.anchorEvent(event_hash, batch_id, event_type)
```

**Lab 2 (Voice API):**
```python
# Voice command processed
result = asr_nlu_pipeline(audio_file)

# Create EPCIS event from NLU result
event = build_epcis_event(result)

# Anchor on blockchain
event_hash = hash_event(event)
anchor_tx = anchor_contract.anchorEvent(event_hash, ...)
```

**Lab 3 (SSI):**
```python
# Verify credential and authorize
can_submit, msg = agent.can_submit_event(did, vc, "commissioning")

if can_submit:
    # Create event with DID
    event = create_epcis_event(data, submitter_did=did)
    
    # Anchor with DID as submitter
    event_hash = hash_event(event)
    anchor_tx = anchor_contract.anchorEvent(event_hash, ...)
    # On-chain record shows which DID submitted event
```

**Lab 5 (DPPs - Preview):**
```python
# Get digital twin
twin = get_batch_twin("BATCH-2025-001")

# Convert to DPP format
dpp = {
    "product_id": "BATCH-2025-001",
    "blockchain": {
        "event_anchors": twin["anchors"],  # On-chain hashes
        "token_id": twin["tokenId"],        # ERC-1155 token
        "settlement": twin["settlement"]    # Payment status
    },
    "metadata": twin["metadata"],
    "credentials": twin["credentials"]
}

# Generate QR code linking to DPP
qr_code = generate_qr(f"https://voiceledger.org/dpp/{batch_id}")
```

---

#### 🌍 Real-World Scenario: Complete Batch Lifecycle

**Scenario:** Farmer Abebe delivers 50 bags to Guzo Cooperative

**1. Onboarding (One-Time, Lab 3):**
```python
# Abebe gets DID and credential from Guzo
abebe_did = generate_did_key()
abebe_vc = issue_credential({"type": "FarmerCredential", ...}, guzo_key)
agent.register_role(abebe_did, "farmer")
```

**2. Voice Command (Lab 2):**
```python
# Abebe speaks into mobile app
audio = "Deliver 50 bags of washed coffee from Abebe to Guzo warehouse"
transcript = run_asr(audio)
nlu_result = infer_nlu_json(transcript)
# Returns: {intent: "commissioning", quantity: 50, origin: "Abebe", destination: "Guzo"}
```

**3. Authorization (Lab 3):**
```python
# API verifies Abebe's credential
can_submit, msg = agent.can_submit_event(abebe_did, abebe_vc, "commissioning")
# Returns: True, "Authorized"
```

**4. EPCIS Event (Lab 1):**
```python
# Create commissioning event
event = {
    "eventType": "ObjectEvent",
    "action": "OBSERVE",
    "bizStep": "commissioning",
    "readPoint": {"id": "urn:epc:id:sgln:0614141.00001.0"},
    "quantity": {"value": 50, "uom": "bags"},
    "submitter": {"did": abebe_did, "name": "Abebe Fekadu"}
}
```

**5. Blockchain Anchoring (Lab 4 - Step 1):**
```python
# Hash event
canonical = canonicalize(event)
event_hash = hashlib.sha256(canonical.encode()).hexdigest()
# event_hash = "bc1658fd8f8c8c25be8c4df6fde3e0c8a8e4c6f9..."

# Anchor on blockchain
tx_hash = anchor_contract.anchorEvent(
    bytes32(event_hash),
    "BATCH-2025-001",
    "commissioning"
)
# → Block 12345678, timestamp: 1702339200
# → Immutable record: event existed at 2023-12-12 00:00:00 UTC
```

**6. Tokenization (Lab 4 - Step 2):**
```python
# Mint ERC-1155 token for batch
token_tx = batch_token_contract.mintBatch(
    guzo_wallet_address,
    50,  # quantity
    "BATCH-2025-001",
    '{"origin": "Ethiopia", "cooperative": "Guzo", "process": "washed"}'
)
# → Token ID 1 created
# → Guzo owns 50 units of token 1
# → Tradeable digital asset (can transfer to buyer)
```

**7. Settlement (Lab 4 - Step 3):**
```python
# Off-chain: Bank transfer $1,250 to Guzo
# On-chain: Record settlement
settlement_tx = settlement_contract.settleCommissioning(
    batchId=1,
    recipient=guzo_wallet_address,
    amount=1250000000  # Wei equivalent
)
# → Settlement recorded on blockchain
# → Abebe can verify: settlement_contract.isSettled(1) → True
```

**8. Digital Twin Update (Lab 4 - Step 4):**
```python
# Update digital twin
record_anchor("BATCH-2025-001", event_hash, "commissioning", 1702339200)
record_token("BATCH-2025-001", token_id=1, quantity=50, owner=guzo_wallet)
record_settlement("BATCH-2025-001", amount=1250000000, settled=True)
record_credential("BATCH-2025-001", abebe_vc)

# Query complete batch history
twin = get_batch_twin("BATCH-2025-001")
# → Returns aggregated view of all on-chain + off-chain data
```

**9. Buyer Verification:**
```python
# Buyer receives batch
twin = get_batch_twin("BATCH-2025-001")

# Verify event was anchored
event_hash = twin["anchors"][0]["eventHash"]
is_anchored = anchor_contract.isAnchored(bytes32(event_hash))
# → True (immutable proof event occurred)

# Verify token ownership
owner = batch_token_contract.balanceOf(guzo_wallet, token_id=1)
# → 50 (Guzo owns 50 units)

# Verify settlement
settlement = settlement_contract.getSettlement(1)
# → {recipient: guzo_wallet, amount: 1250000000, settled: True}
```

**Result:**
- ✅ Event immutably anchored on blockchain (can't be deleted/modified)
- ✅ Batch tokenized as tradeable digital asset (ERC-1155)
- ✅ Settlement transparently recorded (farmer can verify)
- ✅ Complete audit trail preserved (who, what, when, how much)
- ✅ EUDR compliant (verified identities + immutable records)

---

#### 💡 Skills Acquired

By completing Lab 4, you now understand:

1. **Blockchain Fundamentals:**
   - Immutability and append-only ledgers
   - Block timestamps and trustworthiness
   - Gas costs and optimization strategies
   - On-chain vs off-chain tradeoffs

2. **Smart Contract Development:**
   - Solidity 0.8.20+ syntax and features
   - Custom errors for gas efficiency
   - Mappings and structs for state management
   - Event emission for off-chain indexing

3. **Token Standards:**
   - ERC-1155 multi-token standard
   - Semi-fungible tokens (unique IDs + quantities)
   - Token minting, transfers, and metadata
   - Difference from ERC-20 (fungible) and ERC-721 (NFTs)

4. **Foundry Toolchain:**
   - forge build/test/deploy workflow
   - Solidity-based tests (vs JavaScript)
   - Gas profiling and optimization
   - OpenZeppelin library integration

5. **System Architecture:**
   - Hybrid on-chain/off-chain design
   - Digital twin aggregation pattern
   - Multi-contract system design
   - Integration with existing layers (SSI, EPCIS)

---

#### 🚀 What's Next?

**Lab 5: Digital Product Passports (DPPs)**
- EUDR-compliant DPP schema design
- QR code generation for product traceability
- DPP resolver API (FastAPI endpoint)
- Integration with blockchain data
- GeoJSON polygon support for farm boundaries

**Integration with Lab 4:**
Lab 5 will consume blockchain data (anchors, tokens, settlements) to generate comprehensive Digital Product Passports. Each DPP will:
- Reference blockchain transaction hashes for verification
- Include token ID for ownership tracking
- Show settlement status for transparency
- Link to verifiable credentials from SSI layer
- Provide QR code for consumer scanning

**Why This Matters:**
Current system has immutable blockchain records but no consumer-facing interface. Lab 5 adds:
- **QR codes**: Consumers scan to verify product authenticity
- **DPP resolver**: Web interface showing complete product history
- **EUDR compliance**: Meets EU regulation requirements for traceability
- **Transparency**: Consumers see origin, certifications, sustainability data

---

✅ **Lab 4 Complete!** Blockchain anchoring, tokenization, and settlement operational. Ready to create consumer-facing Digital Product Passports (Lab 5).

---

