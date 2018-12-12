import arcpy
import arcpy.management as mgmt

import os.path
import math


def create_points_template():

    POINTS_FEATURE_DATASET = r'Points'
    POINTS_TEMPLATE = r'Points\PointsTemplate'

    workspace = arcpy.env.workspace
    scratch = arcpy.env.scratchWorkspace
    arcpy.env.addOutputsToMap = False

    sr = arcpy.env.outputCoordinateSystem
    if sr is None:
        arcpy.AddError('Geoprocessing environment not set: outputCoordinateSystem')
        exit(-1)

    temp_fc = os.path.join(scratch, os.path.basename(POINTS_TEMPLATE) + '_Temp')
    mgmt.CreateFeatureclass(*os.path.split(temp_fc), 'POINT', spatial_reference=sr)
    mgmt.AddField(temp_fc, 'ELEVATION', 'DOUBLE')
    mgmt.AddField(temp_fc, 'TIME', 'TEXT', field_length=64)
    mgmt.AddField(temp_fc, 'NAME', 'TEXT', field_length=64)
    mgmt.AddField(temp_fc, 'DESCRIPTION', 'TEXT', field_length=64)
    mgmt.AddField(temp_fc, 'SYMBOL', 'TEXT', field_length=64)
    mgmt.AddField(temp_fc, 'TYPE', 'TEXT', field_length=64)
    mgmt.AddField(temp_fc, 'SAMPLES', 'LONG')

    mgmt.CreateFeatureDataset(workspace, POINTS_FEATURE_DATASET, spatial_reference=sr)
    mgmt.CopyFeatures(temp_fc, os.path.join(workspace, POINTS_TEMPLATE))


def dms_degrees(dms):
    # Convert degrees-minutes-seconds to decimal degrees.
    # DMS is passed as a single float of the form DDD.MMSSssss... or
    # a tuple of values (deg, min, sec) or (deg, min). Minutes and seconds
    # must be in the half-open non-negative interval [0.0,60.0).

    if type(dms) == float:
        # split into a tuple
        deg = int(dms)
        dms = math.fabs(dms - deg) * 100.0
        min = int(dms)
        sec = (dms - min) * 100.0

    elif (type(dms) == list or type(dms) == tuple) and len(dms) == 3:
        deg, min, sec = dms

    elif (type(dms) == list or type(dms) == tuple) and len(dms) == 2:
        deg, min = dms
        sec = (min - int(min)) * 60.0
        min = int(min)

    else:
        raise ValueError('Bad DMS value: ' + str(dms))

    if min < 0.0 or sec < 0.0:
        raise ValueError('Negative min/sec value: min=%s sec=%s' % (min, sec))

    if min >= 60.0 or sec >= 60.0:
        raise ValueError('Bad min/sec value: min=%s sec=%s' % (min, sec))

    if deg != int(deg) or min != int(min):
        raise ValueError('Non-integer deg/min: deg=%s min=%s' % (deg, min))

    decimal = min/60.0 + sec/3600.0
    decimal = (deg - decimal) if deg < 0 else (deg + decimal)

    return decimal


if __name__ == '__main__':

    values = (123.45, (123, 45), (123, 45, 00.0), -123.45, (-123, 45))
    values += (123.4530, (123, 45,30.01), 123.453001, (-123, 45, 30.01), -123.453001)
    values += ((123.0, 45.5001666667), (-123.0, 45.5001666667))
    values += ((-123.0, -45.5001666667), (-123.0, 45.0, -30.01))
    values += (123.60, (123.0, 60.25), 123.4560, (123, 45, 60.0))
    values += ((123.125, 45.0, 30.0), (123.0, 45.0125), (123.0, 45.0125, 20.0))

    for v in values:
        try:
            if type(v) is float:
                print('%25.8f  -> %14.8f' % (v, dms_degrees(v)))
            else:
                print('%25s  -> %14.8f' % (v, dms_degrees(v)))

        except ValueError as e:
            print('%25s  ->   Exception: %s' % (v, e))
