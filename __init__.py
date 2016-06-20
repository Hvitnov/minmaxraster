# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ViewshedAnalysis
                                 A QGIS plugin
 ------description-------
                             -------------------
        begin                : 2013-05-22
        copyright            : (C) 2013 by Zoran Čučković 
        email                : 
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


def name():
    return "MinMaxRaster"


def description():
    return "Finds Highest and/or lowest point within a vector polygon on a Digital Elevation Model"


def version():
    return "Version 1.0"


def icon():
    return "icon.png"


def qgisMinimumVersion():
    return "2.0"

def author():
    return "Jakob Hvitnov"

def email():
    return "n/a"

def classFactory(iface):
    # load MinMaxRaster class from file MinMaxRaster
    from MinMaxRaster import MinMaxRaster
    return MinMaxRaster(iface)
