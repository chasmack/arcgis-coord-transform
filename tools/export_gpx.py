import arcpy
import arcpy.management as mgmt
import arcpy.analysis as anlys

import os.path
from datetime import datetime
import xml.etree.ElementTree as etree
import xml.dom.minidom as minidom


#
# ExportGPX - Create a GPX file from point features
#

def export_gpx(wpt_fc, rte_fc, rtept_fc, gpx_file):

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
    GCS_WGS_84 = arcpy.SpatialReference(4326)

    ns_list = (
        (
            'xmlns',
            'http://www.topografix.com/GPX/1/1',
            'http://www.topografix.com/GPX/1/1/gpx.xsd'
        ),(
            'xmlns:wptx1',
            'http://www.garmin.com/xmlschemas/WaypointExtension/v1',
            # Xerces 2.8 validator can't handle Garmin's https redirect
            # 'http://www8.garmin.com/xmlschemas/WaypointExtensionv1.xsd'
            'http://garmin.cmack.org/xmlschemas/WaypointExtensionv1.xsd'
        )
    )
    attrib = dict(creator='ArcGIS Coordinate Transform', version='1.1')
    attrib['xmlns:xsi'] = 'http://www.w3.org/2001/XMLSchema-instance'
    attrib['xsi:schemaLocation'] = ' '.join(item for ns in ns_list for item in ns[1:3])
    attrib.update((ns[0:2] for ns in ns_list))

    gpx = etree.Element('gpx', attrib=attrib)
    meta = etree.SubElement(gpx, 'metadata')
    time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    etree.SubElement(meta, 'time').text = time

    if wpt_fc:
        for fc in wpt_fc.split(';'):

            fields = ['SHAPE@XY'] + [f[0] for f in WPT_FIELDS]
            with arcpy.da.SearchCursor(fc, fields, spatial_reference=GCS_WGS_84) as cur:
                for row in cur:
                    coords = row[0]
                    lon, lat = ('%.8f' % c for c in coords)
                    wpt = etree.SubElement(gpx, 'wpt', attrib={'lat': lat, 'lon': lon})

                    for (field, tag), value in zip(WPT_FIELDS, row[1:]):
                        tag = tag.rsplit(':')[-1]
                        if value is None or value == '':
                            continue
                        elif field == 'ELEVATION':
                            etree.SubElement(wpt, tag).text = '%.4f' % value
                        elif field == 'NAME':
                            etree.SubElement(wpt, tag).text = '%04d' % int(value)
                        elif field == 'SAMPLES':
                            # gpx:extensions/wptx1:WaypointExtension/wptx1:Samples
                            ext = etree.SubElement(wpt, 'extensions')
                            wptx1 = etree.SubElement(ext, 'wptx1:WaypointExtension')
                            etree.SubElement(wptx1, 'wptx1:Samples').text = str(value)
                        else:
                            etree.SubElement(wpt, tag).text = value

    if rte_fc:

        # Explode the route polylines into points
        temp_fc = os.path.join(scratch, os.path.basename(rte_fc) + '_Temp')
        mgmt.FeatureVerticesToPoints(rte_fc, temp_fc)

        # Ensure we have a ROUTE_NAME field
        rte_fields = [f.name for f in arcpy.ListFields(temp_fc, '*NAME')]
        if 'ROUTE_NAME' in rte_fields:
            pass
        elif 'NAME' in rte_fields:
            mgmt.AlterField(temp_fc, 'NAME', 'ROUTE_NAME', 'ROUTE_NAME')
        else:
            mgmt.AddField(temp_fc, 'ROUTE_NAME', 'TEXT', field_length=32)

        # Create unique, non-NULL route names
        with arcpy.da.UpdateCursor(temp_fc, ['ROUTE_NAME', 'ORIG_FID']) as cur:
            for row in cur:
                name, fid = row
                if name is None or name == '':
                    row[0] = 'R%02d' % fid
                else:
                    row[0] = 'R%02d-%s' % (fid, name)
                cur.updateRow(row)

        # Route name and polyline vertex coords
        fields = ['ROUTE_NAME', 'SHAPE@']

        if rtept_fc:
            # Get coordinates for nearest route point
            search_radius = '0.1 foot'
            anlys.Near(temp_fc, rtept_fc, search_radius, location=True)

            # Join fields from the route points
            mgmt.JoinField(temp_fc, 'NEAR_FID', rtept_fc, 'OBJECTID')

            # Add additional fields to the query
            fields += ['NEAR_FID', 'NEAR_X', 'NEAR_Y'] + [f[0] for f in WPT_FIELDS]

        with arcpy.da.SearchCursor(temp_fc, fields, sql_clause=('', 'ORDER BY OBJECTID')) as cur:

            # Near coords are in the temp_fc coordinate system.
            sr = arcpy.Describe(temp_fc).spatialReference

            rtept_number = 0
            last_route = None
            for row in cur:
                route_name = row[0]
                if route_name != last_route:
                    # Start a new route
                    rte = etree.SubElement(gpx, 'rte')
                    etree.SubElement(rte, 'name').text = route_name
                    last_route = route_name
                    rtept_prefix = route_name.partition('-')[0]
                    rtept_number = 0

                rtept_number += 1

                if rtept_fc and row[2] > 0:

                    # Use the near coordinates
                    coords = row[3:5]
                    geom = arcpy.PointGeometry(arcpy.Point(*coords), sr)
                    pt = geom.projectAs(GCS_WGS_84).firstPoint
                    lon, lat = ['%.8f' % c for c in (pt.X, pt.Y)]
                    rtept = etree.SubElement(rte, 'rtept', attrib={'lat': lat, 'lon': lon})

                    # Add remaining route point info
                    for (field, tag), value in zip(WPT_FIELDS, row[5:]):
                        tag = tag.rsplit(':')[-1]
                        if value is None or value == '':
                            continue
                        elif field == 'ELEVATION':
                            etree.SubElement(rtept, tag).text = '%.4f' % value
                        elif field == 'NAME':
                            etree.SubElement(rtept, tag).text = '%s-%04d' % (rtept_prefix, int(value))
                        elif field == 'SAMPLES':
                            # gpx:extensions/wptx1:WaypointExtension/wptx1:Samples
                            ext = etree.SubElement(rtept, 'extensions')
                            wptx1 = etree.SubElement(ext, 'wptx1:WaypointExtension')
                            etree.SubElement(wptx1, 'wptx1:Samples').text = str(value)
                        else:
                            etree.SubElement(rtept, tag).text = value
                else:

                    # Use the polyline vertex coordinates
                    geom = row[1]
                    pt = geom.projectAs(GCS_WGS_84).firstPoint
                    lon, lat = ['%.8f' % c for c in (pt.X, pt.Y)]
                    rtept = etree.SubElement(rte, 'rtept', attrib={'lat': lat, 'lon': lon})

                    # No route point info available
                    etree.SubElement(rtept, 'name').text = '%s-%04d' % (rtept_prefix, rtept_number)

    # with open(gpx_file, 'wb') as f:
    #     etree.ElementTree(gpx).write(f)

    # Reparse the etree gpx with minidom and write pretty xml.
    dom = minidom.parseString(etree.tostring(gpx, encoding='utf-8'))

    with open(gpx_file, 'w') as f:
        dom.writexml(f, addindent='  ', newl='\n', encoding='utf-8')

    return


class ExportGPX(object):
    def __init__(self):
        self.label = "Export GPX"
        self.description = "Create a GPX file from waypoint and route point features."
        self.category = None
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []

        # Input waypoint feature class
        param = arcpy.Parameter(
            displayName='Input Waypoint Features (Optional)',
            name='wpt_fc',
            datatype='GPFeatureLayer',
            parameterType='Optional',
            direction='Input',
            multiValue=True
        )
        param.filter.list = ['Point']
        params.append(param)

        # Input route line feature class
        param = arcpy.Parameter(
            displayName='Input Route Lines (Optional)',
            name='rte_fc',
            datatype='GPFeatureLayer',
            parameterType='Optional',
            direction='Input',
            multiValue=False
        )
        param.filter.list = ['Polyline']
        params.append(param)

        # Input route point feature class
        param = arcpy.Parameter(
            displayName='Input Route Points (Optional)',
            name='rtept_fc',
            datatype='GPFeatureLayer',
            parameterType='Optional',
            direction='Input',
            multiValue=False
        )
        param.filter.list = ['Point']
        params.append(param)

        # Output GPX File
        param = arcpy.Parameter(
            displayName='Output GPX File',
            name='gpx_file',
            datatype='DEFile',
            parameterType='Required',
            direction='Output'
        )
        param.filter.list = ['gpx']
        params.append(param)

        return params

    def execute(self, params, messages):
        wpt_fc = params[0].valueAsText
        rte_fc = params[1].valueAsText
        rtept_fc = params[2].valueAsText
        gpx_file = params[3].valueAsText

        export_gpx(wpt_fc, rte_fc, rtept_fc, gpx_file)

        return


if __name__ == '__main__':

    wpt_fc = arcpy.GetParameterAsText(0)
    rte_fc = arcpy.GetParameterAsText(1)
    rtept_fc = arcpy.GetParameterAsText(2)
    gpx_file = arcpy.GetParameterAsText(3)

    export_gpx(wpt_fc, rte_fc, rtept_fc, gpx_file)
