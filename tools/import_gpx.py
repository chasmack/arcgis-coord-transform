import arcpy
import arcpy.management as mgmt
import os.path
from dateutil import parser, tz, utils
import xml.etree.ElementTree as etree

from tools.utils import create_points_feature_class


#
# ImportGPX - Create waypoint, route point and track features from a GPX file
#

def import_gpx(gpx_file, wpt_fc, trk_fc):

    GCS_WGS_84 = arcpy.SpatialReference(4326)
    GCS_TRANSFORMS = 'WGS_1984_(ITRF08)_To_NAD_1983_2011; NAD_1927_To_NAD_1983_NADCON'

    arcpy.env.geographicTransformations = arcpy.env.geographicTransformations or GCS_TRANSFORMS
    arcpy.AddMessage('Geographic Transformations: %s' % arcpy.env.geographicTransformations)

    scratch = arcpy.env.scratchWorkspace
    arcpy.env.addOutputsToMap = False

    WPT_FIELDS = [
        ('ELEVATION', 'gpx:ele'),
        ('TIME', 'gpx:time'),
        ('NAME', 'gpx:name'),
        ('DESCRIPTION', 'gpx:desc'),
        ('SYMBOL', 'gpx:sym'),
        ('TYPE', 'gpx:type'),
        ('SAMPLES', 'gpx:extensions/wptx1:WaypointExtension/wptx1:Samples')
    ]

    ns = {
        'gpx': 'http://www.topografix.com/GPX/1/1',
        'gpxx': 'http://www.garmin.com/xmlschemas/GpxExtensions/v3',
        'wptx1': 'http://www.garmin.com/xmlschemas/WaypointExtension/v1',
        'ctx': 'http://www.garmin.com/xmlschemas/CreationTimeExtension/v1',
    }

    etree.register_namespace('', 'http://www.topografix.com/GPX/1/1')
    etree.register_namespace('gpxx', 'http://www.garmin.com/xmlschemas/GpxExtensions/v3')
    etree.register_namespace('wptx1', 'http://www.garmin.com/xmlschemas/WaypointExtension/v1')
    etree.register_namespace('ctx', 'http://www.garmin.com/xmlschemas/CreationTimeExtension/v1')

    gpx = etree.parse(gpx_file).getroot()

    sr = arcpy.env.outputCoordinateSystem

    if wpt_fc:
        create_points_feature_class(wpt_fc, sr)

        waypoints = []
        for wpt in gpx.findall('gpx:wpt', ns):
            x, y = wpt.get('lon'), wpt.get('lat')
            row = [arcpy.PointGeometry(arcpy.Point(x, y), GCS_WGS_84).projectAs(sr)]
            for field, tag in WPT_FIELDS:
                elem = wpt.find(tag, ns)

                if elem is None:
                    row.append(None)
                elif field == 'ELEVATION':
                    row.append('%0.4f' % (float(elem.text) / sr.metersPerUnit))
                elif field == 'NAME' and elem.text.isdigit():
                    row.append('%d' % int(elem.text))
                else:
                    row.append(elem.text)
            waypoints.append(row)

        if waypoints:
            fields = ['SHAPE@'] + [f[0] for f in WPT_FIELDS]
            cur = arcpy.da.InsertCursor(wpt_fc, fields)
            for row in waypoints:
                cur.insertRow(row)
            del cur

    if trk_fc:

        # idle time between trkpts to start a new track segment
        TRKSEG_IDLE_SECS = 600

        tracks = []
        track_num = 0
        for trk in gpx.findall('gpx:trk', ns):
            track_num += 1
            elem = trk.find('gpx:name', ns)
            if elem is None:
                track_name = 'track-%04d' % track_num
            else:
                track_name = elem.text

            track_pts = []
            dt_last = None
            segment_num = 0
            for trkpt in trk.findall('./gpx:trkseg/gpx:trkpt', ns):
                x, y = trkpt.get('lon'), trkpt.get('lat')
                pt = arcpy.PointGeometry(arcpy.Point(x, y), GCS_WGS_84).projectAs(sr).firstPoint

                # See if there's a track point time
                elem = trkpt.find('gpx:time', ns)
                if elem is None:
                    dt_last = None
                else:
                    dt = utils.default_tzinfo(parser.parse(elem.text), tz.UTC)
                    if dt_last and (dt - dt_last).seconds > TRKSEG_IDLE_SECS:
                        # start a new segment
                        if len(track_pts) > 1:
                            segment_num += 1
                            if segment_num > 1:
                                segment_name = '%s SEG-%04d' % (track_name, segment_num)
                            else:
                                segment_name = track_name
                            geom = arcpy.Polyline(arcpy.Array(track_pts), sr)
                            tracks.append([geom , segment_name, len(track_pts)])
                        else:
                            arcpy.AddMessage('Skipping track "%s": track_pts=%d' % (track_name, len(track_pts)))
                        track_pts = []
                    dt_last = dt

                track_pts.append(pt)

            if len(track_pts) > 1:
                segment_num += 1
                if segment_num > 1:
                    segment_name = '%s SEG-%04d' % (track_name, segment_num)
                else:
                    segment_name = track_name
                geom = arcpy.Polyline(arcpy.Array(track_pts), sr)
                tracks.append([geom, segment_name, len(track_pts)])
            else:
                arcpy.AddMessage('Skipping track "%s": track_pts=%d' % (track_name, len(track_pts)))

        if tracks:
            temp_fc = os.path.join(scratch, os.path.basename(trk_fc) + '_Temp')
            if sr is None:
                arcpy.AddError('Geoprocessing environment not set: outputCoordinateSystem')
                return None

            fc = mgmt.CreateFeatureclass(*os.path.split(temp_fc), geometry_type='POLYLINE', spatial_reference=sr)
            mgmt.AddField(fc, 'NAME', 'TEXT', field_length=64)
            mgmt.AddField(fc, 'POINTS', 'LONG')

            cur = arcpy.da.InsertCursor(fc, ('SHAPE@', 'NAME', 'POINTS'))
            for row in tracks:
                cur.insertRow(row)
            del cur

            mgmt.CopyFeatures(temp_fc, trk_fc)
            del fc


class ImportGPX(object):
    def __init__(self):
        self.label = "Import GPX"
        self.description = "Create waypoint, route point and track features from a GPX file."
        self.category = None
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []

        # Input GPX File
        param = arcpy.Parameter(
            displayName='Input GPX File',
            name='gpx_file',
            datatype='DEFile',
            parameterType='Required',
            direction='Input'
        )
        param.filter.list = ['gpx']
        params.append(param)

        # Output waypoint feature class
        param = arcpy.Parameter(
            displayName='Output Waypoint Feature Class',
            name='wpt_fc',
            datatype='GPFeatureLayer',
            parameterType='Optional',
            direction='Output'
        )
        params.append(param)

        # Output track feature class
        param = arcpy.Parameter(
            displayName='Output Track Feature Class',
            name='trk_fc',
            datatype='GPFeatureLayer',
            parameterType='Optional',
            direction='Output'
        )
        params.append(param)

        return params

    def execute(self, params, messages):
        gpx_file = params[0].valueAsText
        wpt_fc = params[1].valueAsText
        trk_fc = params[2].valueAsText

        import_gpx(gpx_file, wpt_fc, trk_fc)

        return


if __name__ == '__main__':

    gpx_file = arcpy.GetParameterAsText(0)

    wpt_fc = arcpy.GetParameterAsText(1)
    trk_fc = arcpy.GetParameterAsText(2)

    import_gpx(gpx_file, wpt_fc, trk_fc)
