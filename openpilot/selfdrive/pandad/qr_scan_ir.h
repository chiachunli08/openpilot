#pragma once

#include <charconv>
#include <cstdint>
#include <string_view>

// UI renews this CLOCK_BOOTTIME timestamp every 0.5 s. A stalled or exited UI
// must never leave driver-monitoring illumination disabled indefinitely.
inline int qr_scan_ir_power(int automatic_power, std::string_view heartbeat, uint64_t now,
                            bool is_onroad, bool driver_view) {
  if (is_onroad || !driver_view || heartbeat.empty() || heartbeat.size() > 20) return automatic_power;

  uint64_t timestamp = 0;
  const auto [end, error] = std::from_chars(heartbeat.data(), heartbeat.data() + heartbeat.size(), timestamp);
  if (error != std::errc{} || end != heartbeat.data() + heartbeat.size() || timestamp == 0 || timestamp > now) {
    return automatic_power;
  }
  return now - timestamp < 2000000000ULL ? 0 : automatic_power;
}
