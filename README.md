### ArcGIS Coordinate Transform

Projected geographic coordinates have several advantages for the land surveyor. 
Geographic points and linework drop directly onto aerial imagery and inexpensive handheld 
GPS receivers can be used for search.

However many small and medium size projects use local coordinates, ground distances 
and true or record bearings. Local coordinates are familiar, and mapping is often 
recorded with a true or record basis of bearings. 

The ArcGIS Pro tools in this project provide a link between the local project coordinates 
and projected geographic data in a GIS project. 

The tools use the geoprocessing environment variables `workspace` and `outputCoordinateSystem`. 
The tools also assume points are saved in a Feature Dataset called Points and use a 
Feature Class template called Points\PointsTemplate. Initialize the points templare 
from the ArcGIS Pro Python window -

    sys.path.insert(0, r'D:\Projects\Python\ArcGIS_Coord_Transform')
    from tools.utils import create_points_template
    create_points_template()

Start by creating project boundaries and other features using traditional CAD tools. 
Create points and export a PNEZD points file. Import these local points into an ArcGIS 
geodatabase with the Import PNEZD tool using no transform.

Next, set up an ArcGIS Pro project using an appropriate projected coordinate system. 
Create a feature class with one or more projected geographic points in the ArcGIS project. 
These points represent the target positions for corresponding local points. Initially this 
might be a rough location picked from an aerial image or geographic coordinates from a map 
or GPS shot.  A single point and rotation will be enough to get started. 

Now use the Calculate Transform tool to generate the four-parameter transform file used to 
import points and linework into the ArcGIS project. Input for the Calculate Transform tool 
can be entered manually or placed into a Transform.xml parameter file. In many cases transform 
parameters will be recalculated as more accurate geographic positions become available. 

Finally, use the Import CAD and Import PNEZD tools with the transform parameters to create 
feature classes and transform coordinates to the projected coordinate system. If in the future 
the transform in updated features can either be reimported using the new transform parameters 
or run through the Transform Features tool, once using the old transform parameters in the 
Inverse direction and again using the new parameters in the Forward direction.

The parameter file has the four parameters for a similarity transform: x/y translation, 
rotation and scale. They are expressed as a0, b0, a1, b1 where -

    a1 = scale * cos(rotate)
    
    b1 = scale * sin(rotate)

    a0 = x1 - a1 * x0 + b1 * y0

    b0 = y1 - b1 * x0 - a1 * y0
