from struct import Struct

class ForzaDataPacket:

    sled_format = '<iIfffffffffffffffffffffffffffffffffffffffffffffffffffiiiii'
    dash_format = '<iIfffffffffffffffffffffffffffffffffffffffffffffffffffiiiiifffffffffffffffffHBBBBBBbbb'
    
    ## The names of the properties in the V2 format called 'car dash'
    sled_props = [
        'is_race_on', 'timestamp_ms',
        'engine_max_rpm', 'engine_idle_rpm', 'current_engine_rpm',
        'acceleration_x', 'acceleration_y', 'acceleration_z',
        'velocity_x', 'velocity_y', 'velocity_z',
        'angular_velocity_x', 'angular_velocity_y', 'angular_velocity_z',
        'yaw', 'pitch', 'roll',
        'norm_suspension_travel_FL', 'norm_suspension_travel_FR',
        'norm_suspension_travel_RL', 'norm_suspension_travel_RR',
        'tire_slip_ratio_FL', 'tire_slip_ratio_FR',
        'tire_slip_ratio_RL', 'tire_slip_ratio_RR',
        'wheel_rotation_speed_FL', 'wheel_rotation_speed_FR',
        'wheel_rotation_speed_RL', 'wheel_rotation_speed_RR',
        'wheel_on_rumble_strip_FL', 'wheel_on_rumble_strip_FR',
        'wheel_on_rumble_strip_RL', 'wheel_on_rumble_strip_RR',
        'wheel_in_puddle_FL', 'wheel_in_puddle_FR',
        'wheel_in_puddle_RL', 'wheel_in_puddle_RR',
        'surface_rumble_FL', 'surface_rumble_FR',
        'surface_rumble_RL', 'surface_rumble_RR',
        'tire_slip_angle_FL', 'tire_slip_angle_FR',
        'tire_slip_angle_RL', 'tire_slip_angle_RR',
        'tire_combined_slip_FL', 'tire_combined_slip_FR',
        'tire_combined_slip_RL', 'tire_combined_slip_RR',
        'suspension_travel_meters_FL', 'suspension_travel_meters_FR',
        'suspension_travel_meters_RL', 'suspension_travel_meters_RR',
        'car_ordinal', 'car_class', 'car_performance_index',
        'drivetrain_type', 'num_cylinders'
    ]

    ## The additional props added in the 'car dash' format
    dash_props = ['position_x', 'position_y', 'position_z',
                  'speed', 'power', 'torque',
                  'tire_temp_FL', 'tire_temp_FR',
                  'tire_temp_RL', 'tire_temp_RR',
                  'boost', 'fuel', 'dist_traveled',
                  'best_lap_time', 'last_lap_time',
                  'cur_lap_time', 'cur_race_time',
                  'lap_no', 'race_pos',
                  'accel', 'brake', 'clutch', 'handbrake',
                  'gear', 'steer',
                  'norm_driving_line', 'norm_ai_brake_diff']
    


    def __init__(self, data):
        self.__dict__.update(zip(_ALL_PROPS, _decode(data)))

    @staticmethod
    def decode(data) -> dict:
        """Parse a raw datagram straight into a fresh ``{prop: value}`` dict.

        Same result as ``ForzaDataPacket(data).to_dict()`` without building an
        intermediate object; this is the per-packet hot path.
        """
        return dict(zip(_ALL_PROPS, _decode(data)))

    @classmethod
    def get_props(cls):
        '''
        Return the list of properties in the data packet, in order
        (the sled fields followed by the dash fields).
        '''

        return list(_ALL_PROPS)



    def to_list(self, attributes):
        '''
        Return the values of this data packet, in order. If a list of 
        attributes are provided, only return those.
        :param attributes: the attributes to return
        :type attributes: list
        '''
        if attributes:
            return([getattr(self, a) for a in attributes])
        

        return([getattr(self, prop_name) for prop_name in _ALL_PROPS])

    def to_dict(self) -> dict:
        """Convert all parsed properties to a dictionary."""
        attrs = self.__dict__
        return {prop: attrs[prop] for prop in _ALL_PROPS if prop in attrs}

    def __repr__(self) -> str:
        return f"ForzaDataPacket(race={self.is_race_on}, rpm={getattr(self, 'current_engine_rpm', 0):.0f}, ts={self.timestamp_ms})"


_ALL_PROPS = tuple(ForzaDataPacket.sled_props + ForzaDataPacket.dash_props)

# FH5 datagrams carry 12 undocumented bytes at offset 232; the sled block sits
# before them and the dash block after. Precompiled structs read both halves
# in place with unpack_from, so no per-packet slicing or format lookup.
_SLED = Struct(ForzaDataPacket.sled_format)
_DASH = Struct('<' + ForzaDataPacket.dash_format[len(ForzaDataPacket.sled_format):])
_DASH_OFFSET = _SLED.size + 12
_MIN_SIZE = _DASH_OFFSET + _DASH.size  # 323


def _decode(data) -> tuple:
    # Reject truncated datagrams instead of letting struct.error escape.
    if len(data) < _MIN_SIZE:
        raise ValueError(
            'telemetry datagram too short: %d bytes (need %d)' % (len(data), _MIN_SIZE)
        )
    return _SLED.unpack_from(data) + _DASH.unpack_from(data, _DASH_OFFSET)
