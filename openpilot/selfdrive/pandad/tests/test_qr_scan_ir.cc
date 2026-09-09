#include <string>

#include "common/tests/native_test.h"
#include "selfdrive/pandad/qr_scan_ir.h"

void test_qr_scan_ir() {
  const uint64_t start = 10000000000ULL;
  const std::string heartbeat = std::to_string(start);
  CHECK(qr_scan_ir_power(72, heartbeat, start, false, true) == 0);
  CHECK(qr_scan_ir_power(90, heartbeat, start + 1999999999ULL, false, true) == 0);
  // After a UI stall, return the current automatic power, not a saved old value.
  CHECK(qr_scan_ir_power(90, heartbeat, start + 2000000000ULL, false, true) == 90);
  CHECK(qr_scan_ir_power(72, "", start, false, true) == 72);  // cancellation
  CHECK(qr_scan_ir_power(72, heartbeat, start, true, true) == 72);  // driving
  CHECK(qr_scan_ir_power(72, heartbeat, start, false, false) == 72);  // normal driver monitoring
  CHECK(qr_scan_ir_power(72, heartbeat, start - 1, false, true) == 72);  // invalid/future clock
  for (const auto &invalid : {"0", "-1", "garbage", "10000000000suffix", "10000000000\n", "999999999999999999999"}) {
    CHECK(qr_scan_ir_power(72, invalid, start, false, true) == 72);
  }
  CHECK(qr_scan_ir_power(0, heartbeat, start + 2000000000ULL, false, true) == 0);
}

int main() {
  return run_native_test(test_qr_scan_ir);
}
