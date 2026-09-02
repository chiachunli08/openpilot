def get_camera_packets(disable_dm: bool) -> list[str]:
  packets = ["narrowRoadCameraState", "wideRoadCameraState"]
  if not disable_dm:
    packets.insert(1, "cabinCameraState")
  return packets
