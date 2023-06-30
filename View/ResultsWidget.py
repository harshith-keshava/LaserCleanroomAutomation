from cgi import test
from cmath import isnan
from PySide2 import QtWidgets
from PySide2.QtWidgets import QWidget, QPushButton, QComboBox, QVBoxLayout, QButtonGroup, QFrame, QHBoxLayout
from PySide2 import QtWebEngineWidgets
from PySide2.QtCore import Qt
from ConfigFiles.TestSettings import TestSettings
from Model.Model import Model
from View.TracedVariables import ThreadTracedVariable
from View.TracedVariables import TracedVariable
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from ConfigFiles.MachineSettings import MachineSettings
import math
import os 

class ResultsWidget(QWidget):
    def __init__(self, testSettings:TestSettings, model:Model, parent=None):
        super().__init__(parent)
        self.model = model
        self.testSettings = testSettings
        self.modelDataReady = ThreadTracedVariable()
        self.resultsLayout = QVBoxLayout()
        self.setLayout(self.resultsLayout)
        self.resultsLayout.setAlignment(Qt.AlignTop)
        self.dataResultsComboBox = QComboBox()
        self.dataResultsComboBox.addItem("LPM Processed")
        self.dataResultsComboBox.addItem("LPM Pixel Deviation")
        self.dataResultsComboBox.addItem("LUT Processed")
        self.dataResultsComboBox.addItem("Summary Chart")
        self.rackButtons = [QPushButton("Rack {rackNum}".format(rackNum = rackIdx + 1)) for rackIdx in range(3)]
        [rackButton.setObjectName("rackButton") for rackButton in self.rackButtons]
        [rackButton.setCheckable(True) for rackButton in self.rackButtons]
        self.rackButtonGroup = QButtonGroup()
        self.rackButtonGroup.setExclusive(True)
        [self.rackButtonGroup.addButton(rackButton, rackIdx + 1) for rackIdx, rackButton in enumerate(self.rackButtons)]
        self.rackButtonFrame = QFrame()
        self.rackButtonLayout = QHBoxLayout(self.rackButtonFrame)
        [self.rackButtonLayout.addWidget(rackButton) for rackButton in self.rackButtons]
        self.browser = QtWebEngineWidgets.QWebEngineView()
        self.browser.setMinimumHeight(850)
        self.resultsLayout.addWidget(self.dataResultsComboBox)
        self.resultsLayout.addWidget(self.rackButtonFrame)
        self.resultsLayout.addWidget(self.browser)
        self.dataResultsComboBox.currentIndexChanged.connect(self.updateResultsPage)
        self.rackButtonFrame.hide()
        self.errorHeatmap = None
        self.LPMProcessedGraph = None
        self.summaryTable = None
        self.emptyGraph = go.Figure()
        self.connectToModel()

    def connectToModel(self):
        self.modelDataReady.valueChanged.connect(self.createProcessedPlots)
        self.model.OnDataReady(lambda : self.updateDataFromModel())
        self.rackButtonGroup.buttonClicked.connect(lambda : self.show_lut_results(self.rackButtonGroup.checkedId()))
   
    def updateDataFromModel(self):
        self.modelDataReady.val = self.model.dataReady.value

    def createProcessedPlots(self):
        if self.model.getResults() is not None:
            self.createLPMrocessedPlot()
            self.createErrorHeatMap()
            self.createSummaryChart()
            self.show_results()

    def createErrorHeatMap(self):
        results = self.model.getResults()
        plotDf = results.copy(deep=True)
        maxError = plotDf.groupby('Pixel')["Pulse Power Deviation"].max().reset_index()
        pixelErrorHeatMap = np.split(maxError["Pulse Power Deviation"].to_numpy(), 7)   
        fig = px.imshow(np.array(pixelErrorHeatMap), text_auto=True)
        fig.update(data=[{'customdata': np.split(maxError["Pixel"].to_numpy(), 7), 'hovertemplate': 'Pixel: %{customdata}<br>'}])
        fig.update_xaxes(showticklabels=False).update_yaxes(showticklabels=False)
        fig.update_layout(title_text='Percent Deviation', title_x=0.5)
        fig.write_html(self.model.saveLocation + "\\MaximumPercentError.html")
        self.errorHeatmap = fig

    def createLPMrocessedPlot(self):
        results = self.model.getResults()
        plotDf = results.copy(deep=True)
        commandedPowerLevels = [powerLevel for powerLevel in np.round_(np.unique(plotDf["Commanded Power"].to_numpy()), 3) if not math.isnan(powerLevel)]
        plotDf["Commanded Power"] = plotDf["Commanded Power"].astype(str)
        passedPixelsDf = plotDf.loc[plotDf["Status"] == "Passed"]
        lowPowerFailedPixelsDf = plotDf.loc[(plotDf["Status"] == "Low Power Failure")]
        highPowerFailedPixelsDf = plotDf.loc[(plotDf["Status"] == "High Power Failure")]
        untestedPixelsDf = plotDf.loc[(plotDf["Status"] == "Untested")]
        criticalFailedPixelsDf = plotDf.loc[(plotDf["Status"] == "No Power Failure")]
        processAcceptance = "Passed"
        if len(plotDf.loc[(plotDf["Process Acceptance"] == False) & (plotDf["Status"] != "Untested")]["Process Acceptance"].to_numpy()) > 0 and self.testSettings._testType == 3:
            processAcceptance = ": Failed"
        fig = px.scatter(passedPixelsDf, x="Pixel", y="Pulse Power Average", color="Commanded Power", error_y="Pulse Power Stdv", color_discrete_sequence=px.colors.qualitative.Vivid, title=self.model.testName + processAcceptance)
        fig.update_xaxes(range=[1, 84])
        ymin = passedPixelsDf["Pulse Power Average"].min() - 20
        ymax = passedPixelsDf["Pulse Power Average"].max() + 20
        fig.update_yaxes(range=[ymin, ymax])
        for powerLevelNum, powerLevel in enumerate(commandedPowerLevels):
            fig.add_hline(y=powerLevel, line_dash="dash", line_color=px.colors.qualitative.Vivid[powerLevelNum])  # dotted ref pwr line
            if self.testSettings._testType == 3:
                fig.add_hrect(y0=powerLevel + powerLevel * (self.testSettings._processTolerance / 100), y1=powerLevel - powerLevel * (self.testSettings._processTolerance / 100), line_width=0, fillcolor=px.colors.qualitative.Vivid[powerLevelNum], opacity=0.2)
        lowPowerFailedPixels = np.unique(lowPowerFailedPixelsDf["Pixel"].to_numpy())
        highPowerFailedPixels = np.unique(highPowerFailedPixelsDf["Pixel"].to_numpy())
        untestedPixels = np.unique(untestedPixelsDf["Pixel"].to_numpy())
        criticalFailedPixels = np.unique(criticalFailedPixelsDf["Pixel"].to_numpy())

        criticalFailedPixelScatter = [sum([[pixel, pixel, None] for pixel in criticalFailedPixels],[]), sum([[ymin, ymax, None] for pixel in criticalFailedPixels],[])]
        lowPowerFailedPixelScatter = [sum([[pixel, pixel, None] for pixel in lowPowerFailedPixels],[]), sum([[ymin, ymax, None] for pixel in lowPowerFailedPixels],[])]
        highPowerFailedPixelScatter = [sum([[pixel, pixel, None] for pixel in highPowerFailedPixels],[]), sum([[ymin, ymax, None] for pixel in highPowerFailedPixels],[])]
        untestedPixelScatter = [sum([[pixel, pixel, None] for pixel in untestedPixels],[]), sum([[ymin, ymax, None] for pixel in untestedPixels],[])]

        fig.add_trace(go.Scatter(
            x=untestedPixelScatter[0],
            y=untestedPixelScatter[1],
            name="Untested", mode='lines', line=dict(color='black', width=2, dash='dash'), 
            hovertemplate='Pixel: %{x}'))
        fig.add_trace(go.Scatter(
            x=lowPowerFailedPixelScatter[0],
            y=lowPowerFailedPixelScatter[1],
            name="Low Power Failure", mode='lines', line=dict(color='red', width=2, dash='dash'),
            hovertemplate='Pixel: %{x}'))
        fig.add_trace(go.Scatter(
            x=highPowerFailedPixelScatter[0],
            y=highPowerFailedPixelScatter[1],
            name="High Power Failure", mode='lines', line=dict(color='red', width=2, dash='dash'),
            hovertemplate='Pixel: %{x}'))
        
        fig.add_trace(go.Scatter(
            x=criticalFailedPixelScatter[0],
            y=criticalFailedPixelScatter[1],
            name="High Power Failure", mode='lines', line=dict(color='red', width=2, dash='dash'),
            hovertemplate='Pixel: %{x}'))

        fig.write_html(self.model.saveLocation + "\\LPM_Graph_Results.html")
        self.LPMProcessedGraph = fig

    def updateResultsPage(self):
        if self.dataResultsComboBox.currentIndex() == 0:
            self.rackButtonFrame.hide()
            self.show_results()
        elif self.dataResultsComboBox.currentIndex() == 1:
            self.rackButtonFrame.hide()
            self.show_results_errorMap()
        elif self.dataResultsComboBox.currentIndex() == 2:
            self.rackButtonFrame.show()
            self.show_lut_results(self.rackButtonGroup.checkedId())
        elif self.dataResultsComboBox.currentIndex() == 3:
            self.rackButtonFrame.hide()
            self.showSummaryChart()

    def show_results_errorMap(self):
        if self.errorHeatmap is not None:
            self.browser.setHtml(self.errorHeatmap.to_html(include_plotlyjs='cdn'))
        else:
            self.browser.setHtml(self.emptyGraph.to_html(include_plotlyjs='cdn'))

    def show_results(self):
        if self.LPMProcessedGraph is not None:
            self.browser.setHtml(self.LPMProcessedGraph.to_html(include_plotlyjs='cdn'))
        else:
            self.browser.setHtml(self.emptyGraph.to_html(include_plotlyjs='cdn'))
    
    def show_lut_results(self, rackNum):
        results = self.model._lutDataManager.results_lut
        if results is not None:
            plotDf = results.copy(deep=True)
            plotDf = plotDf.loc[plotDf["Rack"] == rackNum]
            plotDf["Laser"] = plotDf["Laser"].astype(str)
            fig = px.scatter(plotDf, x="BitNumber", y="BitPower", color="Laser")
            powercalledLimit = go.Scatter(x =[round(self.testSettings._powerCalledLimit * 256), round(self.testSettings._powerCalledLimit * 256)], y=[0, MachineSettings._16BitAnalogMaxPower], mode='lines', line=dict(color='red', width=2, dash='dash'), name="Power Called Limit ") 
            powermodifiedLimit = go.Scatter(x =[round(self.testSettings._powerModifiedLimit * 256), round(self.testSettings._powerModifiedLimit * 256)], y=[0, MachineSettings._16BitAnalogMaxPower], mode='lines', line=dict(color='red', width=2, dash='dash'), name="Power Modified Limit ")
            fig.add_trace(powercalledLimit)
            fig.add_trace(powermodifiedLimit)
            if not os.path.exists(self.model.saveLocation + "\\LUT_Graph_Results_Rack{rack}.png".format(rack=rackNum)):
                fig.write_image(self.model.saveLocation + "\\LUT_Graph_Results_Rack{rack}.png".format(rack=rackNum))
            self.browser.setHtml(fig.to_html(include_plotlyjs='cdn'))
        else:
            self.browser.setHtml(self.emptyGraph.to_html(include_plotlyjs='cdn'))
    
    def createSummaryChart(self):
        import plotly.graph_objects as go
        validRanges = self.model.getValidPixelRanges()
        summary = self.model.getSummary()
        headers = summary[0] + ["Valid Ranges"]
        summaryData = np.array(summary[1:]).T
        fig = go.Figure(data=[go.Table(header=dict(values=headers),
                        cells=dict(values=[summaryData[0], summaryData[1], summaryData[2], summaryData[3], validRanges]))
                            ])
        self.summaryTable = fig

    def showSummaryChart(self):
        if self.summaryTable is not None: 
            self.browser.setHtml(self.summaryTable.to_html(include_plotlyjs='cdn'))
        else:
            self.browser.setHtml(self.emptyGraph.to_html(include_plotlyjs='cdn'))
