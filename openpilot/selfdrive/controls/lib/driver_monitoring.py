def get_force_decel(disable_dm: bool, dm_no_response: bool, soft_disabling: bool) -> bool:
  return bool((not disable_dm and dm_no_response) or soft_disabling)
