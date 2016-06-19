# -*- coding: utf-8 -*-
"""
/***************************************************************************
 MinMaxRaster
                                 A QGIS plugin
 Finds Highest and Lowest point within a polygon on a DEM.

                              -------------------
        begin                : 2016-06-13
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Jakob Hvitnov
        email                : hvitnov@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
# Import the PyQt and QGIS libraries
import sys
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
import resources_rc

from viewshedanalysisdialog import ViewshedAnalysisDialog
from doViewshed import *
from osgeo import osr, gdal
import os
import numpy as np


class ViewshedAnalysis:

    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = QFileInfo(QgsApplication.qgisUserDbFilePath()).path() + "/python/plugins/MinMaxRaster"
        # initialize locale
        localePath = ""
    ## REMOVED .toString()
        locale = str(QSettings().value("locale/userLocale"))[0:2] #to je za jezik
        
        if QFileInfo(self.plugin_dir).exists():
            localePath = self.plugin_dir + "/i18n/MinMaxRaster_" + locale + ".qm"

        if QFileInfo(localePath).exists():
            self.translator = QTranslator()
            self.translator.load(localePath)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = ViewshedAnalysisDialog()

    def initGui(self):
        # Create action that will start plugin configuration
        # icon in the plugin reloader : from resouces.qrc file (compiled)
        self.action = QAction(
            QIcon(":/plugins/MinMaxRaster/icon.png"),
            u"MinMaxRaster", self.iface.mainWindow())
        # connect the action to the run method
        self.action.triggered.connect(self.run)


        # Add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(u"&Viewshed Analysis", self.action)

        # Fire refreshing of combo-boxes containing lists of table columns, after a new layer has been selected
        self.dlg.ui.cmbPoints.currentIndexChanged.connect(self.load_cmbObsField)
        self.dlg.ui.cmbPointsTarget.currentIndexChanged.connect(self.load_cmbTargetField)


    def unload(self):
        # Remove the plugin menu item and icon
        self.iface.removePluginMenu(u"&Viewshed Analysis", self.action)
        self.iface.removeToolBarIcon(self.action)
        
    #This is just a clumsy workaround for the problem of mulitple arguments in the Qt signal-slot scheme
    def load_cmbObsField(self,cmb_index): self.reload_dependent_combos(cmb_index,'cmbObsField')
    def load_cmbTargetField(self,cmb_index): self.reload_dependent_combos(cmb_index-1,'cmbTargetField')
                                                                           #-1 because the first one is empty...          
                   
    def reload_dependent_combos(self,cmb_index,cmb_name):

        if cmb_name=='cmbObsField':
            cmb_obj=self.dlg.ui.cmbObsField
            l=self.dlg.ui.cmbPoints.itemData(cmb_index)   #(self.dlg.ui.cmbPoints.currentIndex())
        else:
            cmb_obj=self.dlg.ui.cmbTargetField
            l=self.dlg.ui.cmbPoints.itemData(cmb_index)   #(self.dlg.ui.cmbPoints.currentIndex())
       
        cmb_obj.clear()
        cmb_obj.addItem('',0)
        
        ly_name=str(l)
        ly = QgsMapLayerRegistry.instance().mapLayer(ly_name)
        
        #QMessageBox.information(self.iface.mainWindow(), "prvi", str(ly_name))
        if ly is None: return
        
        provider = ly.dataProvider()
        columns = provider.fields() # a dictionary
        j=0
        for fld in columns:
            #QMessageBox.information(self.iface.mainWindow(), "drugi", str(i.name))
            j+=1
            cmb_obj.addItem(str(fld.name()),str(fld.name())) #for QGIS 2.0 we need column names, not index (j)

    def printMsg(self, msg):
        QMessageBox.information(self.iface.mainWindow(), "Debug", msg)

    def debugHere(self):
        # Use pdb for debugging
        import pdb
        # These lines allow you to set a breakpoint in the app
        pyqtRemoveInputHook()
        pdb.set_trace()

    def run(self):
        # Use pdb for debugging
        import pdb


        #UBACIVANJE RASTERA I TOCAKA (mora biti ovdje ili se barem pozvati odavde)
        myLayers = []
        iface = self.iface
        #clear combos        
        self.dlg.ui.cmbRaster.clear();self.dlg.ui.cmbPoints.clear();self.dlg.ui.cmbPointsTarget.clear()
        #add an empty value to optional combo
        self.dlg.ui.cmbPointsTarget.addItem('',0)
        #add layers to combos
        for i in range(len(iface.mapCanvas().layers())):
            myLayer = iface.mapCanvas().layer(i)
            if myLayer.type() == myLayer.RasterLayer:

                #provjera da li je DEM 1 band .... !!!
                self.dlg.ui.cmbRaster.addItem(myLayer.name(),myLayer.id())

            elif myLayer.geometryType() == QGis.Point:
                self.dlg.ui.cmbPoints.addItem(myLayer.name(),myLayer.id())
                self.dlg.ui.cmbPointsTarget.addItem(myLayer.name(),myLayer.id())

            elif myLayer.geometryType() == QGis.Polygon:
                self.dlg.ui.cmbPolys.addItem(myLayer.name(), myLayer.id())

        #allAttrs = layer.pendingAllAttributesList()
       
                
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()

        l = self.dlg.ui.cmbPoints.itemData(self.dlg.ui.cmbPoints.currentIndex())
        ly_name = str(l)
        # QMessageBox.information(self.iface.mainWindow(), "drugi", str(ly_name))

        # See if OK was pressed
        if result == 1:

            # Get path for output .shp file
            outPath = ViewshedAnalysisDialog.returnOutputFile(self.dlg)


            ly_obs = ViewshedAnalysisDialog.returnPointLayer(self.dlg)
            ly_target = ViewshedAnalysisDialog.returnTargetLayer(self.dlg)
            ly_poly = ViewshedAnalysisDialog.returnPolyLayer(self.dlg)
            polygon_layer = QgsMapLayerRegistry.instance().mapLayer(ly_poly)
            polygon_path = polygon_layer.dataProvider().dataSourceUri()
            if '|' in polygon_path:
                path_end = polygon_path.find('|')
                polygon_path = polygon_path[:path_end]

            if self.dlg.demFile is None:
                ly_dem = ViewshedAnalysisDialog.returnRasterLayer(self.dlg)
                raster_layer = QgsMapLayerRegistry.instance().mapLayer(ly_dem)
                raster_path = raster_layer.dataProvider().dataSourceUri()
                if '|' in raster_path:
                    path_end = raster_path.find('|')
                    raster_path = raster_path[:path_end]
            else:
                ly_dem = self.dlg.demFile
                raster_path = self.dlg.demFile
                raster_layer = QgsRasterLayer(self.dlg.demFile)

            raster = gdal.Open(raster_path)
            shp = ogr.Open(polygon_path)
            lyr = shp.GetLayer()

            if self.dlg.ui.chkHighest.isChecked():
                # Perform "Find highest / Lowest points algorithm"

                # list to append points when found
                pointList = []

                features = range(lyr.GetFeatureCount())

                for featNo in features:
                    feat = lyr.GetFeature(featNo)
                    # Get raster georeference info
                    transform = raster.GetGeoTransform()
                    xOrigin = transform[0]
                    yOrigin = transform[3]
                    pixelWidth = transform[1]
                    pixelHeight = transform[5]

                    # Reproject vector geometry to same projection as raster
                    sourceSR = lyr.GetSpatialRef()
                    targetSR = osr.SpatialReference()
                    targetSR.ImportFromWkt(raster.GetProjectionRef())
                    coordTrans = osr.CoordinateTransformation(sourceSR, targetSR)
                    geom = feat.GetGeometryRef()

                    # import pdb
                    # These lines allow you to set a breakpoint in the app
                    # pyqtRemoveInputHook()
                    # pdb.set_trace()


                    geom.Transform(coordTrans)

                    # Get extent of feat
                    geom = feat.GetGeometryRef()
                    if (geom.GetGeometryName() == 'MULTIPOLYGON'):
                        count = 0
                        pointsX = [];
                        pointsY = []
                        for polygon in geom:
                            geomInner = geom.GetGeometryRef(count)
                            ring = geomInner.GetGeometryRef(0)
                            numpoints = ring.GetPointCount()
                            for p in range(numpoints):
                                lon, lat, z = ring.GetPoint(p)
                                pointsX.append(lon)
                                pointsY.append(lat)
                            count += 1
                    elif (geom.GetGeometryName() == 'POLYGON'):
                        ring = geom.GetGeometryRef(0)
                        numpoints = ring.GetPointCount()
                        pointsX = [];
                        pointsY = []
                        for p in range(numpoints):
                            lon, lat, z = ring.GetPoint(p)
                            pointsX.append(lon)
                            pointsY.append(lat)

                    else:
                        sys.exit("ERROR: Geometry needs to be either Polygon or Multipolygon")

                    xmin = min(pointsX)
                    xmax = max(pointsX)
                    ymin = min(pointsY)
                    ymax = max(pointsY)

                    # Specify offset and rows and columns to read
                    xoff = int((xmin - xOrigin) / pixelWidth)
                    yoff = int((yOrigin - ymax) / pixelWidth)
                    xcount = int((xmax - xmin) / pixelWidth) + 1
                    ycount = int((ymax - ymin) / pixelWidth) + 1

                    # Create memory target raster
                    target_ds = gdal.GetDriverByName('MEM').Create('', xcount, ycount, 1, gdal.GDT_Byte)
                    target_ds.SetGeoTransform((
                        xmin, pixelWidth, 0,
                        ymax, 0, pixelHeight,
                    ))

                    # Create for target raster the same projection as for the value raster
                    raster_srs = osr.SpatialReference()
                    raster_srs.ImportFromWkt(raster.GetProjectionRef())
                    target_ds.SetProjection(raster_srs.ExportToWkt())

                    # Rasterize zone polygon to raster
                    gdal.RasterizeLayer(target_ds, [1], lyr, burn_values=[1])

                    try:
                        # Read raster as arrays
                        banddataraster = raster.GetRasterBand(1)
                        dataraster = banddataraster.ReadAsArray(xoff, yoff, xcount, ycount).astype(np.float)

                        bandmask = target_ds.GetRasterBand(1)
                        datamask = bandmask.ReadAsArray(0, 0, xcount, ycount).astype(np.int)

                        histogram = False
                        decimals = 0
                        # Calculate statistics of zonal raster`
                        if histogram:
                            if decimals > 0:
                                dataraster = dataraster * pow(10, decimals)
                            dataraster = dataraster.astype(np.int)
                            a = np.bincount((dataraster * datamask).flat, weights=None, minlength=None)
                        else:
                            # Mask zone of raster
                            zoneraster = np.ma.masked_array(dataraster, np.logical_not(datamask))
                            a = [np.average(zoneraster), np.mean(zoneraster), np.median(zoneraster), np.std(zoneraster),
                                 np.var(zoneraster), np.min(zoneraster), np.max(zoneraster)]
                    except:
                        self.printMsg("Error when analyzing!\nAre you sure the polygon layer lies within the DEM raster?")
                        return 0

                    maxis = np.unravel_index(np.argmax(zoneraster), zoneraster.shape)
                    maxis2 = (maxis[1] * pixelWidth + xmin, ymax - maxis[0] * pixelWidth)
                    pointList.append([maxis2[0], maxis2[1], zoneraster[maxis]])

                shpfile = write_high_points(outPath, pointList, raster_layer.crs())

                path = os.path.abspath(shpfile)
                basename = os.path.splitext(os.path.basename(shpfile))[0]
                layer = QgsVectorLayer(path, basename, "ogr")
                QgsMapLayerRegistry.instance().addMapLayer(layer)
                return True



            z_obs = ViewshedAnalysisDialog.returnObserverHeight(self.dlg)
            z_obs_field = self.dlg.ui.cmbObsField.itemData(
                self.dlg.ui.cmbObsField.currentIndex())#table columns are indexed 0-n


            z_target = ViewshedAnalysisDialog.returnTargetHeight(self.dlg)

            z_target_field =self.dlg.ui.cmbTargetField.itemData(
                self.dlg.ui.cmbTargetField.currentIndex())

            Radius = ViewshedAnalysisDialog.returnRadius(self.dlg)

            search_top_obs = ViewshedAnalysisDialog.returnSearchTopObserver(self.dlg)
            search_top_target = ViewshedAnalysisDialog.returnSearchTopTarget(self.dlg)
            
            output_options = ViewshedAnalysisDialog.returnOutputOptions(self.dlg)

            curv=ViewshedAnalysisDialog.returnCurvature(self.dlg)

            refraction = curv[1] if curv else 0

            if not output_options [0]:
                QMessageBox.information(self.iface.mainWindow(), "Error!", str("Select an output option")) 
                return 
             #   LOADING CSV
             # uri = "file:///some/path/file.csv?delimiter=%s&crs=epsg:4723&wktField=%s" \
             # % (";", "shape")

            out_raster = Viewshed(ly_obs, ly_dem, z_obs, z_target, Radius, outPath,
                                 output_options,
                                 ly_target, search_top_obs, search_top_target,
                                 z_obs_field, z_target_field, curv, refraction)
            
            for r in out_raster:
                #QMessageBox.information(self.iface.mainWindow(), "debug", str(r))
                lyName = os.path.splitext(os.path.basename(r))
                layer = QgsRasterLayer(r, lyName[0])
                #if error -> it's shapefile, skip rendering...
                if not layer.isValid():
                    layer= QgsVectorLayer(r,lyName[0],"ogr")

                else:
##                    #rlayer.setColorShadingAlgorithm(QgsRasterLayer.UndefinedShader)
##
##                    #from linfinity.com
##                    extentMin, extentMax = layer.computeMinimumMaximumFromLastExtent( band )
##
##                    # For greyscale layers there is only ever one band
##                    band = layer.bandNumber( layer.grayBandName() ) # base 1 counting in gdal
##                    # We don't want to create a lookup table
##                    generateLookupTableFlag = False
##                    # set the layer min value for this band
##                    layer.setMinimumValue( band, extentMin, generateLookupTableFlag )
##                    # set the layer max value for this band
##                    layer.setMaximumValue( band, extentMax, generateLookupTableFlag )
##
##                    # let the layer know that the min max are user defined
##                    layer.setUserDefinedGrayMinimumMaximum( True )
##
##                    # make sure the layer is redrawn
##                    layer.triggerRepaint()

                    #NOT WORKING 
                    
##                    x = QgsRasterTransparency.TransparentSingleValuePixel()
##                    x.pixelValue = 0
##                    x.transparencyPercent = 100
##                    layer.setTransparentSingleValuePixelList( [ x ] )
                    
                    layer.setContrastEnhancement(QgsContrastEnhancement.StretchToMinimumMaximum)

                    #rlayer.setDrawingStyle(QgsRasterLayer.SingleBandPseudoColor)
                    #rlayer.setColorShadingAlgorithm(QgsRasterLayer.PseudoColorShader)
                    #rlayer.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum, False)
                    #rlayer.setTransparency(200)
                    #rlayer.setNoDataValue(0.0)
                    
                QgsMapLayerRegistry.instance().addMapLayer(layer)

            
#    adding csv files ... an attempt
##                    url = QUrl.fromLocalFile(r)
##                    url.addQueryItem('delimiter',',')
##                    url.addQueryItem('xField  <-or-> yField','longitude')
##                    url.addQueryItem('crs','epsg:4723')
##                    url.addQueryItem('wktField','WKT')
## -> Problem
##                    #layer_uri=Qstring.fromAscii(url.toEncoded())
##                    layer_uri= str(url)
##                    layer=QgsVectorLayer(r, lyName[0],"delimitedtext")

#                     QMessageBox.information(None, "File created!", str("Please load file manually (as comma delilmited text)."))

