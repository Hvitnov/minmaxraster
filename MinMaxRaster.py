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
import ogr
import sys
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
import resources_rc

from MinMaxRasterDialog import MinMaxRasterDialog
from osgeo import osr, gdal
import os
import numpy as np


class MinMaxRaster:
    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = QFileInfo(QgsApplication.qgisUserDbFilePath()).path() + "/python/plugins/MinMaxRaster"

        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'LOS_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = MinMaxRasterDialog()

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&MinMaxRaster Tool')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'MinMaxRaster')
        self.toolbar.setObjectName(u'MinMaxRaster')

        #set up progress dialog for calculations
        self.progress = QProgressDialog()
        self.progress.setWindowTitle("MinMaxRaster")
        self.progress.setLabelText("Analyzing Data")
        self.progress.setCancelButton(None)

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('MinMaxRaster', message)

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        # Plugin Builder way - lets skip that
        # icon_path = ':/plugins/LOS/icon.png'
        # self.add_action(
        #    icon_path,
        #    text=self.tr(u'Find suitable antenna placements'),
        #    callback=self.run,
        #    parent=self.iface.mainWindow())

        # Much more simple way - from Zoran Čučković's viewshed plug
        self.action = QAction(QIcon(":/plugins/MinMaxRaster/icon.png"),
                              u"MinMaxRaster", self.iface.mainWindow())

        # connect the action to the run method
        self.action.triggered.connect(self.run)

        # Add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(u"&MinMaxRaster", self.action)

    def unload(self):
        # Remove the plugin menu item and icon - also from Zoran Čučković's vievshed
        self.iface.removePluginMenu(u"&MinMaxRaster", self.action)
        self.iface.removeToolBarIcon(self.action)


    def printMsg(self, msg):
        QMessageBox.information(self.iface.mainWindow(), "Debug", msg)

    def debugHere(self):
        import pdb
        # These lines allow you to set a breakpoint in the app
        pyqtRemoveInputHook()
        pdb.set_trace()

    def run(self):
        # clear and repopulate layer comboboxes
        self.dlg.ui.rasterLayerSelector.clear()
        self.dlg.ui.polygonLayerSelector.clear()

        for i in range(len(self.iface.mapCanvas().layers())):
            mapLayer = self.iface.mapCanvas().layer(i)
            if mapLayer.type() == mapLayer.RasterLayer:
                self.dlg.ui.rasterLayerSelector.addItem(mapLayer.name(),mapLayer.id())

            elif mapLayer.geometryType() == QGis.Polygon:
                self.dlg.ui.polygonLayerSelector.addItem(mapLayer.name(), mapLayer.id())

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()

        # If OK is pressed
        if result == 1:
            # Get path for output .shp file - if not selected, use temp file in home dir
            if self.dlg.outputFile is not None:
                outPath = MinMaxRasterDialog.getOutputFilePath(self.dlg)
            else:
                outPath = os.path.expanduser('~') + "/tempFile"

            # Load Layers from Comboboxes
            if self.dlg.polyFile is None:
                polygon_layer_path = MinMaxRasterDialog.getPolygonSelection(self.dlg)
                polygon_map_layer = QgsMapLayerRegistry.instance().mapLayer(polygon_layer_path)
                polygon_path = polygon_map_layer.dataProvider().dataSourceUri()
                if '|' in polygon_path:
                    path_end = polygon_path.find('|')
                    polygon_path = polygon_path[:path_end]
            else:
                polygon_path = self.dlg.polyFile

            if self.dlg.demFile is None:
                raster_layer_path = MinMaxRasterDialog.getRasterSelection(self.dlg)
                raster_map_layer = QgsMapLayerRegistry.instance().mapLayer(raster_layer_path)
                raster_path = raster_map_layer.dataProvider().dataSourceUri()
                if '|' in raster_path:
                    path_end = raster_path.find('|')
                    raster_path = raster_path[:path_end]
            else:
                raster_path = self.dlg.demFile
                raster_map_layer = QgsRasterLayer(self.dlg.demFile)


            # Import layers into GDAL Dataset (raster) and OGR Layer (polygon)
            raster_layer = gdal.Open(raster_path)
            ogr_poly = ogr.Open(polygon_path)
            poly_layer = ogr_poly.GetLayer()

            # Get raster geotransform
            # ("Coefficients for transforming between pixel/line (P,L) raster space,
            # and projection coordinates (Xp,Yp) space.") - GDAL API
            transform = raster_layer.GetGeoTransform()
            xOrigin = transform[0]
            yOrigin = transform[3]
            pixelWidth = transform[1]
            pixelHeight = transform[5]

            # list to append high or low points when found - used to write .shpfile later
            pointsForSHP = []

            # get the number of polygon features to iterate over
            # This should really be done using .getFeatures() which returns an iterator,
            # but OGR layer has no such method
            features = range(poly_layer.GetFeatureCount())

            # Set and display progressbar
            self.progress.setMinimum(1)
            self.progress.setMaximum(len(features) - 1)
            self.progress.show()

            # Perform "Find highest / Lowest points algorithm"
            for featNo in features:
                feat = poly_layer.GetFeature(featNo)

                # Reproject vector geometry to same projection as raster
                poly_spatial_reference = poly_layer.GetSpatialRef()
                raster_spatial_reference = osr.SpatialReference()
                raster_spatial_reference.ImportFromWkt(raster_layer.GetProjectionRef())
                transformation = osr.CoordinateTransformation(poly_spatial_reference, raster_spatial_reference)
                geom = feat.GetGeometryRef()
                geom.Transform(transformation)

                # Get points in feature perifery
                if (geom.GetGeometryName() == 'POLYGON'):
                    # Get geometry as set of lineStrings
                    feature_perifery = geom.GetGeometryRef(0)

                    numpoints = feature_perifery.GetPointCount()
                    pointsX = []
                    pointsY = []

                    for p in range(numpoints):
                        lon, lat, z = feature_perifery.GetPoint(p)
                        pointsX.append(lon)
                        pointsY.append(lat)

                    # Store feature extent
                    xmin = min(pointsX)
                    xmax = max(pointsX)
                    ymin = min(pointsY)
                    ymax = max(pointsY)

                else:
                    sys.exit("ERROR: Wrong geometry for polygon layer")

                # Specify offset and rows and columns to read
                xoff = int((xmin - xOrigin) / pixelWidth)
                yoff = int((yOrigin - ymax) / pixelWidth)
                xcount = int((xmax - xmin) / pixelWidth) + 1
                ycount = int((ymax - ymin) / pixelWidth) + 1

                # Create GDAL Raster in memory to represent polygon for analysis
                raster_in_memory = gdal.GetDriverByName('MEM').Create('', xcount, ycount, 1, gdal.GDT_Byte)
                # Memory raster gets extent of polygon layer
                raster_in_memory.SetGeoTransform((xmin, pixelWidth, 0, ymax, 0, pixelHeight,))
                # Memory raster gets projection of raster layer
                raster_in_memory.SetProjection(raster_spatial_reference.ExportToWkt())
                # Polygon outline is drawn (burned) to Memory raster
                gdal.RasterizeLayer(raster_in_memory, [1], poly_layer, burn_values=[1])

                try:
                    # Read raster layer as numpy arrays
                    raster_band = raster_layer.GetRasterBand(1)
                    raster_array = raster_band.ReadAsArray(xoff, yoff, xcount, ycount).astype(np.float)

                    # Read Memory raster layer as numpy arrays - to serve as mask for original raster
                    raster_mask_band = raster_in_memory.GetRasterBand(1)
                    raster_mask = raster_mask_band.ReadAsArray(0, 0, xcount, ycount).astype(np.int)

                    # Use the mask array to set 'Not' values outside polygon area and get correct analysis area
                    analysis_raster = np.ma.masked_array(raster_array, np.logical_not(raster_mask))

                    # Get indices of max and min values inside the polygon
                    results = [np.argmax(analysis_raster), np.argmin(analysis_raster)]
                except:
                    self.printMsg("Error when analyzing!\nAre you sure the polygon layer lies within the DEM raster?")
                    return 0

                # indices as as x,y values
                max_array_index = np.unravel_index(results[0], analysis_raster.shape)
                min_array_index = np.unravel_index(results[1], analysis_raster.shape)

                # x-y values transformed to map values
                max_map_point = (max_array_index[1] * pixelWidth + xmin, ymax - max_array_index[0] * pixelWidth)
                min_map_point = (min_array_index[1] * pixelWidth + xmin, ymax - min_array_index[0] * pixelWidth)

                # Add point to list of points to write in shapefile after analysis
                if self.dlg.ui.OutputTypeSelector.currentIndex() == 0:
                    pointsForSHP.append([max_map_point[0], max_map_point[1], analysis_raster[max_array_index], 'max'])
                else:
                    pointsForSHP.append([min_map_point[0], min_map_point[1], analysis_raster[min_array_index], 'min'])

                self.progress.setValue(featNo)

            # Write points to shapefile
            shpfile = self.write_points_layer(outPath, pointsForSHP, raster_map_layer.crs())

            # add shapefile as QGIS layer
            path = os.path.abspath(shpfile)
            basename = os.path.splitext(os.path.basename(shpfile))[0]
            layer = QgsVectorLayer(path, basename, "ogr")
            QgsMapLayerRegistry.instance().addMapLayer(layer)

            return True

    def write_points_layer(self, file_name, data_list, coordinate_ref_system):
        fields = QgsFields()
        fields.append(QgsField("Type", QVariant.String, 'string', 5))
        fields.append(QgsField("Height", QVariant.Double, 'double', 10, 3))
        writer = QgsVectorFileWriter(file_name + ".shp", "CP1250", fields,
                                     QGis.WKBPoint, coordinate_ref_system)  # , "ESRI Shapefile"
        # CP... = encoding
        if writer.hasError() != QgsVectorFileWriter.NoError:
            QMessageBox.information(None, "ERROR!", "Cannot write point file (?)")
            return 0

        for data in data_list:
            # create a new feature
            feat = QgsFeature()

            # Write point data
            point = QgsPoint(data[0], data[1])
            feat.setGeometry(QgsGeometry.fromPoint(point))
            feat.setFields(fields)
            feat['Type'] = str(data[3])
            feat['Height'] = float(data[2])
            writer.addFeature(feat)
            del feat
        del writer
        return file_name + ".shp"
