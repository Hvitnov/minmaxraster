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

from PyQt4 import QtGui
from ui_MinMaxRaster import Ui_MinMaxRaster
import os

class MinMaxRasterDialog(QtGui.QDialog):
   
    def __init__(self):
        QtGui.QDialog.__init__(self)
        
        # Set up the user interface from UI files
        self.ui = Ui_MinMaxRaster()
        self.ui.setupUi(self)

        # Connect buttons
        self.ui.btn_BrowseForOutputFile.clicked.connect(self.createOutputFile)
        self.ui.btn_BrowseForDemFile.clicked.connect(self.getDemFile)
        self.ui.btn_BrowseForPolyFile.clicked.connect(self.getPolyFile)

        # set files up for check
        self.demFile = None
        self.polyFile = None
        self.outputFile = None

    def getPolygonSelection(self):
        layer = self.ui.polygonLayerSelector.itemData(self.ui.polygonLayerSelector.currentIndex())
        return str(layer)
    
    def getRasterSelection(self):
        layer = self.ui.rasterLayerSelector.itemData(self.ui.rasterLayerSelector.currentIndex())
        return str(layer)
    
    def getOutputFilePath(self):
        path = self.ui.input_outputPath.toPlainText()
        return str(path)

    def createOutputFile(self):
        home = os.path.expanduser('~')
        filename = QtGui.QFileDialog.getSaveFileName(self, 'Save File', home, '*')
        self.outputFile = filename
        try :
            fname = open(filename, 'w')
            self.ui.input_outputPath.clear()
            self.ui.input_outputPath.insertPlainText(self.outputFile)
            fname.close()
        except:
            pass

    def getDemFile(self):
        '''Returns the raster file selected by User - or from disk if a path is provided in the GUI'''
        home = os.path.expanduser('~')
        filename = QtGui.QFileDialog.getOpenFileName(self, 'Open DEM file', home, '*.tif')
        self.demFile = filename
        try:
            fname = open(filename, 'r')
            self.ui.input_rasterFilePath.clear()
            self.ui.input_rasterFilePath.insertPlainText(self.demFile)
            fname.close()
        except:
            pass

    def getPolyFile(self):
        '''Returns the Vector file selected by User - or from disk if a path is provided in the GUI'''
        home = os.path.expanduser('~')
        filename = QtGui.QFileDialog.getOpenFileName(self, 'Open polygon file', home, '*.shp')
        self.polyFile = filename
        try:
            fname = open(filename, 'r')
            self.ui.input_polyFilePath.clear()
            self.ui.input_polyFilePath.insertPlainText(self.polyFile)
            fname.close()
        except:
            pass
