#!/usr/bin/env python3
import cereal.messaging as messaging
from openpilot.common.params import Params
from openpilot.common.realtime import Ratekeeper, config_realtime_process
from openpilot.system.hardware import driver_camera_available


def disabled_driver_monitoring_state():
  """Build a valid, attentive state for hardware without a driver camera."""
  dat = messaging.new_message('driverMonitoringState', valid=True)
  dat.driverMonitoringState = {
    "events": [],
    "faceDetected": False,
    "isDistracted": False,
    "distractedType": 0,
    "awarenessStatus": 1.0,
    "stepChange": 0.0,
    "awarenessActive": 1.0,
    "awarenessPassive": 1.0,
    "isLowStd": True,
    "hiStdCount": 0,
    "isActiveMode": False,
    "isRHD": False,
    "uncertainCount": 0,
  }
  return dat


def disabled_dmonitoringd_thread():
  config_realtime_process([0, 1, 2, 3], 5)
  pm = messaging.PubMaster(['driverMonitoringState'])
  rk = Ratekeeper(20, print_delay_threshold=None)

  while True:
    pm.send('driverMonitoringState', disabled_driver_monitoring_state())
    rk.keep_time()


def dmonitoringd_thread():
  if not driver_camera_available():
    disabled_dmonitoringd_thread()
    return

  from openpilot.selfdrive.monitoring.helpers import DriverMonitoring

  config_realtime_process([0, 1, 2, 3], 5)

  params = Params()
  pm = messaging.PubMaster(['driverMonitoringState'])
  sm = messaging.SubMaster(['driverStateV2', 'liveCalibration', 'carState', 'selfdriveState', 'modelV2',
                            'carControl'], poll='driverStateV2')

  DM = DriverMonitoring(rhd_saved=params.get_bool("IsRhdDetected"), always_on=params.get_bool("AlwaysOnDM"))
  demo_mode=False

  # 20Hz <- dmonitoringmodeld
  while True:
    sm.update()
    if not sm.updated['driverStateV2']:
      # iterate when model has new output
      continue

    valid = sm.all_checks()
    if demo_mode and sm.valid['driverStateV2']:
      DM.run_step(sm, demo=demo_mode)
    elif valid:
      DM.run_step(sm, demo=demo_mode)

    # publish
    dat = DM.get_state_packet(valid=valid)
    pm.send('driverMonitoringState', dat)

    # load live always-on toggle
    if sm['driverStateV2'].frameId % 40 == 1:
      DM.always_on = params.get_bool("AlwaysOnDM")
      demo_mode = params.get_bool("IsDriverViewEnabled")

    # save rhd virtual toggle every 5 mins
    if (sm['driverStateV2'].frameId % 6000 == 0 and not demo_mode and
     DM.wheelpos.prob_offseter.filtered_stat.n > DM.settings._WHEELPOS_FILTER_MIN_COUNT and
     DM.wheel_on_right == (DM.wheelpos.prob_offseter.filtered_stat.M > DM.settings._WHEELPOS_THRESHOLD)):
      params.put_bool_nonblocking("IsRhdDetected", DM.wheel_on_right)

def main():
  dmonitoringd_thread()


if __name__ == '__main__':
  main()
