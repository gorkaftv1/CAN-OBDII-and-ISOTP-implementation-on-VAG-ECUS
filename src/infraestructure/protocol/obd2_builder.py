"""Concrete OBD-II protocol builder backed by the config PID registry.

All request byte sequences are read directly from :mod:`config.obd_pids`
— no byte literals appear in this module's method bodies.
"""

from __future__ import annotations

import config.obd_pids as _pids
from core.interfaces.i_protocol_builder import IProtocolBuilder


class Obd2ProtocolBuilder(IProtocolBuilder):
    """Concrete implementation of :class:`~core.interfaces.i_protocol_builder.IProtocolBuilder`.

    Delegates every method to the centralised PID registry in
    :mod:`config.obd_pids`, ensuring that request frames are always
    consistent with the single source of truth defined there.  No byte
    literals, no logic, and no I/O appear in this class.
    """

    # ------------------------------------------------------------------ #
    # Mode 0x01 — Current Data (Live Data)                               #
    # ------------------------------------------------------------------ #

    def build_read_rpm_request(self) -> bytes:
        """Build the Mode 0x01 / PID 0x0C request payload for Engine RPM."""
        return _pids.PIDS[0x0C].request

    def build_read_coolant_temp_request(self) -> bytes:
        """Build the Mode 0x01 / PID 0x05 request payload for Coolant Temperature."""
        return _pids.PIDS[0x05].request

    def build_read_vehicle_speed_request(self) -> bytes:
        """Build the Mode 0x01 / PID 0x0D request payload for Vehicle Speed."""
        return _pids.PIDS[0x0D].request

    def build_read_throttle_position_request(self) -> bytes:
        """Build the Mode 0x01 / PID 0x11 request payload for Throttle Position."""
        return _pids.PIDS[0x11].request

    def build_read_engine_load_request(self) -> bytes:
        """Build the Mode 0x01 / PID 0x04 request payload for Calculated Engine Load."""
        return _pids.PIDS[0x04].request

    # ------------------------------------------------------------------ #
    # Mode 0x03 — Request Stored Diagnostic Trouble Codes                #
    # ------------------------------------------------------------------ #

    def build_read_dtcs_request(self) -> bytes:
        """Build the Mode 0x03 request payload for reading stored DTCs."""
        return _pids.READ_DTCS_REQUEST

    # ------------------------------------------------------------------ #
    # Mode 0x04 — Clear / Reset Diagnostic Information                   #
    # ------------------------------------------------------------------ #

    def build_clear_dtcs_request(self) -> bytes:
        """Build the Mode 0x04 request payload for clearing stored DTCs."""
        return _pids.CLEAR_DTCS_REQUEST

    # ------------------------------------------------------------------ #
    # Mode 0x09 — Request Vehicle Information                            #
    # ------------------------------------------------------------------ #

    def build_read_vin_request(self) -> bytes:
        """Build the Mode 0x09 / InfoType 0x02 request payload for the VIN."""
        return _pids.VIN_PID_REQUEST
