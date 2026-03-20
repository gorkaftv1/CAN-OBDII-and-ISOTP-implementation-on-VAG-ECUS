"""CAN bus and protocol constants derived from the Arduino ECU simulator.

All values in this module are taken verbatim from ``ecu_protocol.h`` and
``ecu_sim.ino``.  Do **not** modify these constants without first verifying
the change against the Arduino source.
"""

# ────────────────────────────────────────────────────────────────────────────
# CAN Bus
# ────────────────────────────────────────────────────────────────────────────

CAN_BITRATE: int = 500_000          # CAN bus speed in bits per second (500 kbps)
CAN_TX_ID: int = 0x7E0              # CAN ID used by the scanner to address the ECU
CAN_RX_ID: int = 0x7E8             # CAN ID on which the ECU sends its responses

# ────────────────────────────────────────────────────────────────────────────
# ISO-TP Transport Layer (ISO 15765-2)
# ────────────────────────────────────────────────────────────────────────────

ISOTP_PADDING_BYTE: int = 0xAA     # Byte used to pad CAN frames to 8 bytes
ISOTP_SF_MAX_PAYLOAD: int = 7      # Maximum data bytes in a Single Frame
ISOTP_FF_DATA_BYTES: int = 6       # Data bytes carried in the First Frame
ISOTP_CF_DATA_BYTES: int = 7       # Data bytes carried in each Consecutive Frame
ISOTP_FC_TIMEOUT_MS: int = 1000    # Maximum wait time (ms) for a Flow Control frame
ISOTP_CF_SEPARATION_MS: int = 25   # Minimum separation time (ms) between Consecutive Frames

# Protocol Control Information (PCI) type nibbles (upper nibble of PCI byte)
ISOTP_PCI_SF: int = 0x00           # PCI type: Single Frame
ISOTP_PCI_FF: int = 0x10           # PCI type: First Frame
ISOTP_PCI_CF: int = 0x20           # PCI type: Consecutive Frame
ISOTP_PCI_FC: int = 0x30           # PCI type: Flow Control frame

# ────────────────────────────────────────────────────────────────────────────
# OBD-II Application Layer
# ────────────────────────────────────────────────────────────────────────────

OBD_MODE_LIVE_DATA: int = 0x01     # Mode 01: request current powertrain data
OBD_MODE_READ_DTCS: int = 0x03     # Mode 03: request stored Diagnostic Trouble Codes
OBD_MODE_CLEAR_DTCS: int = 0x04    # Mode 04: clear stored DTCs and freeze-frame data
OBD_MODE_VEHICLE_INFO: int = 0x09  # Mode 09: request vehicle information (e.g. VIN)

OBD_POSITIVE_OFFSET: int = 0x40   # Added to the request mode byte to form a positive response
OBD_NEGATIVE_PREFIX: int = 0x7F   # First byte of every Negative Response Code (NRC) frame

# ────────────────────────────────────────────────────────────────────────────
# NRC Codes (Negative Response Codes defined in the simulator)
# ────────────────────────────────────────────────────────────────────────────

NRC_SERVICE_NOT_SUPPORTED: int = 0x11      # Requested service / mode is not implemented
NRC_SUBFUNCTION_NOT_SUPPORTED: int = 0x12  # PID or sub-function within the mode is not supported
NRC_INVALID_MESSAGE_FORMAT: int = 0x13     # Request frame is malformed or has wrong length
NRC_CONDITIONS_NOT_CORRECT: int = 0x22     # ECU state prevents handling the request (e.g. engine running for Mode 04)
NRC_REQUEST_OUT_OF_RANGE: int = 0x31       # PID value is outside the supported range
NRC_SECURITY_ACCESS_DENIED: int = 0x33    # Request rejected due to insufficient security access level
