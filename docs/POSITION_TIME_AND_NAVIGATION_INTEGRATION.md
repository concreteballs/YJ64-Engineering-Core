# Position, Time and Navigation Integration

## Purpose and boundaries

Define a shared source-aware position/time service for marine navigation, field assistance, robotics, scientific observations and emergency operation. It is a platform service, not a replacement for chartplotters, certified navigation equipment or discipline-specific navigation systems. Routine navigation integrations and the optional Emergency Celestial Navigation module remain separate.

## Position acquisition

Continuously discover and, when permitted, use available sources:
- multi-constellation GNSS receivers (GPS, Galileo, GLONASS, BeiDou and compatible augmentation services);
- external GNSS receivers and marine instruments;
- operating-system fused location, cellular and Wi-Fi positioning, and permitted Bluetooth/beacon sources;
- connected vessel/vehicle data such as speed log, heading, gyrocompass, AIS-derived context and instrument gateways;
- manual fixes, surveyed landmarks and celestial-navigation observations.

Every observation records source/device identity, coordinate reference system and datum, acquisition time, age, accuracy/uncertainty, integrity flags, permission state and provenance. Distinguish an absolute fix from a network estimate, sensor-derived estimate, dead-reckoned position or manually entered value. Keep the last trusted fix and its uncertainty; never silently overwrite history.

## Dead reckoning and sensor fusion

When GNSS is unavailable, estimate movement using calibrated accelerometer/gyroscope, magnetometer/heading, barometer, external speed log, wheel/propeller sensors and vehicle/vessel state where available. Apply sensor calibration, bias and drift models, orientation and mounting transforms, and environment-specific constraints. Weather, wind, current, waves and terrain may constrain or explain motion but are not direct position measurements.

Uncertainty must grow with elapsed time and travelled distance unless a justified independent observation reduces it. Expose covariance/error bounds, source contributions and confidence. Reacquired absolute fixes may correct the current estimate while retaining the pre-correction track, residuals and correction event. Flag implausible jumps, sensor disagreement, magnetic disturbance, spoofing/jamming indicators and stale sources. Do not promise reliable long-duration phone-only inertial navigation.

## Time acquisition and discipline

Maintain an internal UTC estimate linked to a monotonic clock, with uncertainty, drift estimate and source history. Candidate sources include GNSS time, trusted network time, cellular time where exposed, external instruments, peer devices and manual input. Keep UTC/TAI/TT/UT1 or other scientific time scales explicit where relevant; keep timezone and local display formatting separate from absolute time.

A peer device that recently synchronized online is only a candidate time source. Evaluate its last synchronization timestamp, source, uncertainty, drift, clock-change history and integrity. Compare multiple sources where possible. Detect manual wall-clock changes and timezone changes independently. Apply internal corrections with provenance rather than blindly copying peer time or changing Android system time. For observations, retain both raw device timestamp and corrected UTC estimate.

## Navigation application integration

YJ64 must not recreate mature chart databases or routine marine navigation applications by default. Build a Navigation Integration Hub that evaluates and uses supported provider APIs, official SDKs, documented exports and standards such as NMEA 0183, NMEA 2000, Signal K and GPX where appropriate. Candidate ecosystems include OpenCPN, Signal K, commercial charting/anchoring products and external marine instruments.

For each provider, record exact product/version, API availability, permission model, licence/terms, offline behaviour, supported data direction and limitations. Never assume Navionics or another commercial application exposes an unrestricted public API; do not scrape protected chart data or bypass licensing. YJ64 retains its own canonical route/waypoint/track representations and provenance.

## Emergency Celestial Navigation module

Expose as a separately invokable optional module, not as a mandatory part of routine navigation. It may guide users through improvised angle-measuring tools, calibration, observation planning, time recording, sight reduction, multiple lines of position, running fixes and uncertainty assessment. It must explain that a single altitude observation normally defines a line of position, not a unique two-dimensional fix. Require suitable additional observations or an independent prior constraint. Clearly distinguish a homemade plumb-bob/protractor instrument from a precision marine sextant and quantify realistic limitations.

Offline operation requires preloaded ephemerides, leap-second/time-scale data as applicable, sight-reduction tables or validated algorithms, a clear observation log and printable/manual fallback procedures. The module must report missing inputs and uncertainty rather than manufacture a position.

## Security, privacy and safety

Location permissions are granular and explained. Network-derived location may reveal sensitive movement; use minimum necessary access and local processing where possible. External device data is untrusted until identified and validated. Detect spoofing/jamming indicators and preserve raw observations for audit. A smartphone is a supplementary aid, not the sole safety-critical navigation instrument.

## Acceptance criteria

- Position and time observations preserve source, timestamp, uncertainty, datum/time scale and provenance.
- Last trusted fix survives process restart and offline operation.
- Dead reckoning exposes increasing uncertainty and can be corrected without erasing the original track.
- Timezone changes are not mistaken for UTC changes; peer-device synchronization is assessed rather than blindly trusted.
- Provider adapters use documented/licensed interfaces and state unsupported operations clearly.
- Emergency celestial navigation works offline with versioned ephemerides and transparent error bounds.
- Spoofed, stale, inconsistent or implausible data is flagged and never silently promoted to trusted state.

## Status

Planned. No general source-fusion, time-discipline, dead-reckoning, marine-app integration hub or emergency celestial-navigation implementation is claimed.
