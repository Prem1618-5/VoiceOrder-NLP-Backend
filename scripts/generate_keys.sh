#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# VoiceOrder — RS256 Keypair Generator
#
# Generates a 2048-bit RSA keypair for JWT signing (RS256).
# Run once per deployment environment (dev, staging, prod).
#
# Usage:
#   chmod +x scripts/generate_keys.sh
#   bash scripts/generate_keys.sh
#
# Output:
#   private.pem  — kept secret; used to SIGN tokens   → JWT_PRIVATE_KEY env var
#   public.pem   — shareable; used to VERIFY tokens   → JWT_PUBLIC_KEY env var
#
# Both files are excluded from git via .gitignore.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

PRIVATE_KEY_FILE="private.pem"
PUBLIC_KEY_FILE="public.pem"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   VoiceOrder — RS256 Keypair Generator              ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Generate private key ──────────────────────────────────────────────────────
echo "▸ Generating 2048-bit RSA private key…"
openssl genrsa -out "$PRIVATE_KEY_FILE" 2048 2>/dev/null
echo "  ✔ Private key written to $PRIVATE_KEY_FILE"

# ── Extract public key ────────────────────────────────────────────────────────
echo "▸ Extracting public key…"
openssl rsa -in "$PRIVATE_KEY_FILE" -pubout -out "$PUBLIC_KEY_FILE" 2>/dev/null
echo "  ✔ Public key written to $PUBLIC_KEY_FILE"

# ── Display key summaries ─────────────────────────────────────────────────────
echo ""
echo "Key fingerprints:"
echo "  Private key bits : $(openssl rsa -in $PRIVATE_KEY_FILE -text -noout 2>/dev/null | grep 'Private-Key' | grep -o '[0-9]*')"
echo "  Public key bits  : $(openssl rsa -in $PUBLIC_KEY_FILE -pubin -text -noout 2>/dev/null | grep 'Public-Key' | grep -o '[0-9]*')"

# ── .env file instructions ────────────────────────────────────────────────────
echo ""
echo "────────────────────────────────────────────────────────"
echo " LOCAL DEV (.env file)"
echo "────────────────────────────────────────────────────────"
echo ""
echo "Add the following to your .env file (paste entire PEM blocks):"
echo ""
echo "JWT_PRIVATE_KEY=$(cat $PRIVATE_KEY_FILE | tr '\n' '\\n')"
echo "JWT_PUBLIC_KEY=$(cat $PUBLIC_KEY_FILE | tr '\n' '\\n')"
echo ""

# ── Railway instructions ──────────────────────────────────────────────────────
echo "────────────────────────────────────────────────────────"
echo " RAILWAY PRODUCTION DEPLOYMENT"
echo "────────────────────────────────────────────────────────"
echo ""
echo "1. Go to your Railway project → Variables"
echo "2. Create variable: JWT_PRIVATE_KEY"
echo "   Value: (paste contents of private.pem)"
echo "3. Create variable: JWT_PUBLIC_KEY"
echo "   Value: (paste contents of public.pem)"
echo ""
echo "Railway accepts multi-line values — paste the full PEM"
echo "including -----BEGIN/END----- headers and newlines."
echo ""

# ── Security reminder ─────────────────────────────────────────────────────────
echo "────────────────────────────────────────────────────────"
echo " ⚠  SECURITY REMINDERS"
echo "────────────────────────────────────────────────────────"
echo ""
echo "  • private.pem → NEVER commit to git (already in .gitignore)"
echo "  • public.pem  → safe to share, but also in .gitignore for cleanliness"
echo "  • Rotate keys: regenerate and redeploy when a key may be compromised"
echo "  • Per Data Security spec: new RS256 keypair per deployment environment"
echo ""
echo "Done. ✔"
echo ""
