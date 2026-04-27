#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# build-ios.sh — Build and install vehicle-diag on iOS (FREE Apple ID)
#
# No Apple Developer account required.
# Uses Xcode free signing — app is valid for 7 days on the device.
#
# Usage:
#   ./scripts/build-ios.sh           # install directly on USB-connected device
#   ./scripts/build-ios.sh --ipa     # build .ipa for AltStore / Sideloadly
#
# Prerequisites:
#   1. Xcode 15+ installed (Mac App Store, free)
#   2. CocoaPods:  sudo gem install cocoapods
#   3. Node 18+:   https://nodejs.org
#   4. Open Xcode → Settings → Accounts → add your Apple ID (free account is fine)
#   5. iPhone/iPad connected via USB, trusted on the device
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
BUNDLE_ID="com.gorka.vehiclediag"
BUILD_MODE="install"   # overridden by --ipa flag

# ── Parse args ────────────────────────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --ipa) BUILD_MODE="ipa" ;;
    *) echo "Unknown argument: $arg"; exit 1 ;;
  esac
done

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
IOS_DIR="$ROOT/ios"
BUILD_DIR="$ROOT/build"
ADAPTER_FACTORY="$ROOT/src/infrastructure/adapterFactory.ts"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}▶ $*${NC}"; }
success() { echo -e "${GREEN}✔ $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠ $*${NC}"; }
err()     { echo -e "${RED}✘ $*${NC}"; exit 1; }

# ── Prerequisite checks ───────────────────────────────────────────────────────
info "Checking prerequisites…"
command -v xcodebuild >/dev/null 2>&1 || err "Xcode not found. Install from the Mac App Store (free)."
command -v pod        >/dev/null 2>&1 || err "CocoaPods not found. Run: sudo gem install cocoapods"
command -v node       >/dev/null 2>&1 || err "Node.js not found. Install from https://nodejs.org"
command -v npx        >/dev/null 2>&1 || err "npx not found. Update Node.js."
success "Prerequisites OK."

# ── Step 1: USE_MOCK = false ──────────────────────────────────────────────────
info "Setting USE_MOCK = false…"
if grep -q "USE_MOCK = true" "$ADAPTER_FACTORY"; then
  sed -i '' 's/export const USE_MOCK = true/export const USE_MOCK = false/' "$ADAPTER_FACTORY"
  success "USE_MOCK → false"
else
  success "USE_MOCK already false."
fi

# Always restore USE_MOCK to true on exit so dev environment is unaffected
trap 'sed -i "" "s/export const USE_MOCK = false/export const USE_MOCK = true/" "$ADAPTER_FACTORY" 2>/dev/null; warn "USE_MOCK restored to true."' EXIT

# ── Step 2: JS dependencies ───────────────────────────────────────────────────
info "Installing JS dependencies…"
cd "$ROOT"
npm install --silent
success "npm install done."

# ── Step 3: Expo prebuild ─────────────────────────────────────────────────────
info "Running expo prebuild (generates ios/ native project)…"
npx expo prebuild --platform ios --clean
success "Prebuild complete."

# ── Step 4: Detect workspace ──────────────────────────────────────────────────
WORKSPACE=$(find "$IOS_DIR" -maxdepth 1 -name "*.xcworkspace" | head -1)
[[ -z "$WORKSPACE" ]] && err "No .xcworkspace found in $IOS_DIR. Prebuild may have failed."
WORKSPACE_NAME=$(basename "$WORKSPACE" .xcworkspace)
SCHEME="$WORKSPACE_NAME"
info "Workspace: $WORKSPACE_NAME  |  Scheme: $SCHEME"

# ── Step 5: Pod install ───────────────────────────────────────────────────────
info "Running pod install…"
cd "$IOS_DIR"
pod install --repo-update
cd "$ROOT"
success "CocoaPods install done."

# ─────────────────────────────────────────────────────────────────────────────
# MODE A: Direct USB install  (default)
# ─────────────────────────────────────────────────────────────────────────────
if [[ "$BUILD_MODE" == "install" ]]; then

  info "Building and installing on connected device via USB…"
  echo ""
  echo -e "${YELLOW}  Make sure your iPhone/iPad is:${NC}"
  echo "    • Connected via USB"
  echo "    • Unlocked and trusted (tap 'Trust' if prompted)"
  echo "    • In Settings → Privacy → Developer Mode (iOS 16+): enabled"
  echo ""
  read -r -p "  Press Enter when ready…"

  # expo run:ios handles free-account signing automatically
  npx expo run:ios \
    --device \
    --configuration Release

  echo ""
  success "════════════════════════════════════════════"
  success " App installed on your device!"
  success "════════════════════════════════════════════"
  echo ""
  echo -e "${YELLOW}  ⚠  Free Apple ID limit: app expires in 7 days.${NC}"
  echo "     To renew: re-run this script (no rebuild needed, just re-sign)."
  echo "     Or install AltStore to auto-renew over WiFi — see --ipa mode."
  echo ""

# ─────────────────────────────────────────────────────────────────────────────
# MODE B: Build .ipa for AltStore / Sideloadly
# ─────────────────────────────────────────────────────────────────────────────
else

  mkdir -p "$BUILD_DIR"
  DERIVED_DATA="$BUILD_DIR/DerivedData"
  IPA_DIR="$BUILD_DIR/ipa"
  mkdir -p "$IPA_DIR"

  info "Building .app (Release, no-codesign for packaging)…"
  xcodebuild \
    -workspace "$IOS_DIR/$WORKSPACE_NAME.xcworkspace" \
    -scheme "$SCHEME" \
    -configuration Release \
    -sdk iphoneos \
    -derivedDataPath "$DERIVED_DATA" \
    -allowProvisioningUpdates \
    CODE_SIGN_STYLE=Automatic \
    CODE_SIGN_IDENTITY="iPhone Developer" \
    PRODUCT_BUNDLE_IDENTIFIER="$BUNDLE_ID" \
    clean build \
    2>&1 | grep -E "^(error:|warning:|Build succeeded|FAILED|===)" || true

  # Locate the built .app
  APP_PATH=$(find "$DERIVED_DATA" -name "*.app" -path "*/Release-iphoneos/*" | head -1)
  [[ -z "$APP_PATH" ]] && err ".app not found in DerivedData. Build failed."
  success "Built: $APP_PATH"

  # Package into .ipa  (Payload/<App>.app zipped)
  info "Packaging .ipa…"
  PAYLOAD_DIR="$BUILD_DIR/Payload"
  rm -rf "$PAYLOAD_DIR"
  mkdir -p "$PAYLOAD_DIR"
  cp -r "$APP_PATH" "$PAYLOAD_DIR/"
  cd "$BUILD_DIR"
  zip -qr "$IPA_DIR/vehiclediag.ipa" Payload
  rm -rf "$PAYLOAD_DIR"
  cd "$ROOT"

  IPA_FILE="$IPA_DIR/vehiclediag.ipa"
  [[ -f "$IPA_FILE" ]] || err ".ipa not created."

  echo ""
  success "════════════════════════════════════════════════"
  success " .ipa ready: $IPA_FILE"
  success "════════════════════════════════════════════════"
  echo ""
  echo -e "${CYAN}How to install without a paid Developer account:${NC}"
  echo ""
  echo "  Option 1 — AltStore (recommended, auto-renews every 7 days):"
  echo "    1. Install AltServer on your Mac: https://altstore.io"
  echo "    2. Install AltStore on your iPhone via AltServer."
  echo "    3. Open AltStore on iPhone → My Apps → ＋ → select vehiclediag.ipa"
  echo "    4. Keep AltServer running on Mac — it refreshes the app via WiFi"
  echo "       when both devices are on the same network."
  echo ""
  echo "  Option 2 — Sideloadly (simpler one-time install):"
  echo "    1. Download Sideloadly: https://sideloadly.io"
  echo "    2. Connect iPhone via USB, drag vehiclediag.ipa into Sideloadly."
  echo "    3. Enter your Apple ID — Sideloadly signs and installs it."
  echo "    4. Re-run every 7 days (or use Sideloadly's auto-refresh)."
  echo ""
  echo "  After installing (both options):"
  echo "    Settings → General → VPN & Device Management → trust your Apple ID."
  echo ""
  echo -e "${YELLOW}  ⚠  Free Apple ID: max 3 app IDs per 7 days on a device.${NC}"
  echo ""

fi
