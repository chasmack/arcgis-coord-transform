import arcpy
import arcpy.management as mgmt
import arcpy.analysis as anlys

import copy
from datetime import datetime
import xml.etree.ElementTree as etree
import xml.dom.minidom as minidom


#
# ExportGPX - Create a GPX file from point features
#

def export_gpx(wpt_fc, gpx_file, create_rte, close_rte):

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

    sr = arcpy.Describe(wpt_fc).spatialReference

    # A list of rte elements to append after the waypoints
    routes = []

    for fc in wpt_fc.split(';'):

        desc = arcpy.Describe(fc)
        hasZ = desc.hasZ

        fc_fields = list(f.name.upper() for f in arcpy.ListFields(fc))
        sql_clause = (None, 'ORDER BY NAME' if 'NAME' in fc_fields else None)

        if create_rte:
            # Add a new rte element to the end of the routes list
            routes.append(etree.Element('rte'))
            etree.SubElement(routes[-1], 'name').text = fc

        closing_rtept = None

        arcpy.AddMessage('Feature Class: ' + fc)
        arcpy.AddMessage('Fields: ' + ', '.join(fc_fields))
        arcpy.AddMessage('Has Z: ' + str(hasZ))

        with arcpy.da.SearchCursor(fc, '*', spatial_reference=GCS_WGS_84, sql_clause=sql_clause) as cur:

            for row in cur:

                row = dict(zip(fc_fields, row))

                coords = row['SHAPE']
                lon, lat = ('%.8f' % c for c in coords[0:2])
                wpt = etree.SubElement(gpx, 'wpt', attrib={'lat': lat, 'lon': lon})

                # Match waypoint elements to feature class fields
                for wpt_field, tag in WPT_FIELDS:
                    tag = tag.rsplit(':')[-1]

                    if wpt_field == 'ELEVATION':
                        if hasZ:
                            etree.SubElement(wpt, tag).text = '%.4f' % (coords[2] * sr.metersPerUnit)
                        else:
                            # Search for elevation field in fc
                            for f in fc_fields:
                                if f.startswith('ELE'):
                                    etree.SubElement(wpt, tag).text = '%.4f' % (row[f] * sr.metersPerUnit)
                                    break

                    elif wpt_field == 'NAME' and 'NAME' in fc_fields:
                        if row['NAME'].isdigit():
                            row['NAME'] = '%04d' % int(row['NAME'])
                        etree.SubElement(wpt, tag).text = row['NAME']

                    elif wpt_field == 'SAMPLES' and 'SAMPLES' in fc_fields:
                        # gpx:extensions/wptx1:WaypointExtension/wptx1:Samples
                        ext = etree.SubElement(wpt, 'extensions')
                        wptx1 = etree.SubElement(ext, 'wptx1:WaypointExtension')
                        etree.SubElement(wptx1, 'wptx1:Samples').text = row['SAMPLES']

                    elif wpt_field in fc_fields:
                        etree.SubElement(wpt, tag).text = row[wpt_field]

                if create_rte:
                    # Create a copy of the waypoint and append it to the route
                    rtept = copy.deepcopy(wpt)
                    rtept.tag = 'rtept'
                    routes[-1].append(rtept)

                    if close_rte and closing_rtept is None:
                        # Keep a copy of the first route point for the closing segment
                        closing_rtept = copy.deepcopy(wpt)
                        closing_rtept.tag = 'rtept'

        if closing_rtept:
            # Append the closing route point
            routes[-1].append(closing_rtept)

    for rte in routes:
        # Append the routes
        gpx.append(rte)

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
            displayName='Input Waypoint Features',
            name='wpt_fc',
            datatype='GPFeatureLayer',
            parameterType='Required',
            direction='Input',
            multiValue=True
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

        # Input enable routes switch
        param = arcpy.Parameter(
            displayName='Create Routes',
            name='create_rte',
            datatype='GPBoolean',
            parameterType='Required',
            direction='Input',
            multiValue=False
        )
        param.value = False
        params.append(param)

        # Input add closing segment switch
        param = arcpy.Parameter(
            displayName='Add Closing Segmant',
            name='close_rte',
            datatype='GPBoolean',
            parameterType='Required',
            direction='Input',
            multiValue=False
        )
        param.value = False
        params.append(param)

        return params

    def execute(self, params, messages):
        wpt_fc = params[0].valueAsText
        gpx_file = params[1].valueAsText
        create_rte = params[2].value
        close_rte = params[3].value

        export_gpx(wpt_fc, gpx_file, create_rte, close_rte)

        return


if __name__ == '__main__':

    wpt_fc = arcpy.GetParameterAsText(0)
    gpx_file = arcpy.GetParameterAsText(1)
    create_rte = arcpy.GetParameter(2)
    close_rte = arcpy.GetParameter(3)

    export_gpx(wpt_fc, gpx_file, create_rte, close_rte)
