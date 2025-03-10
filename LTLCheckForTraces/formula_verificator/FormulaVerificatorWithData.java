package formula_verificator;

import org.deckfour.xes.in.XParser;
import org.deckfour.xes.in.XesXmlGZIPParser;
import org.deckfour.xes.model.XLog;
import org.deckfour.xes.model.XTrace;
import org.processmining.plugins.declareanalyzer.Tester;
import org.processmining.plugins.declareminer.visualizing.*;
import org.processmining.plugins.declareanalyzer.DeclareAnalyzerSingleTracePlugin;

import java.io.File;
import java.util.ArrayList;
import java.util.Date;


public class FormulaVerificatorWithData {

    // the plugin for checking the conformance of a trace
    DeclareAnalyzerSingleTracePlugin analyzer = new DeclareAnalyzerSingleTracePlugin();

    // this is just for testing purposes
    public void analyze() throws Exception {
        String logFile = "/media/sf_SharedFolder/newlog.xes.gz";
        String modelFile = "/media/sf_SharedFolder/newlog_model.xml";

        XParser parser = new XesXmlGZIPParser();
        XLog log = parser.parse(new File(logFile)).get(0);

        DeclareMap model = getModel(modelFile);

        for (XTrace trace : log) {
            analyzer.analyze(trace, model);
        }
    }

    // reads the declare model 
    private static DeclareMap getModel(String fileName) {
        AssignmentViewBroker broker = XMLBrokerFactory.newAssignmentBroker(fileName);
        AssignmentModel model = broker.readAssignment();
        DeclareMap map = new DeclareMap(model, null, null, null, broker, null);
        return map;
    }

    // returns whether the trace is conformant
    // analyzer does the actual analyzing and returns a boolean -> true if trace is conformant
    public boolean verifyTrace(String modelFile,
                               String traceId,
                               ArrayList<String> activities,
                               ArrayList<String> groups,
                               ArrayList<Date> times) {
        DeclareMap model = getModel(modelFile);
        XTrace trace = Tester.genXtrace(traceId, activities, groups, times);

        return analyzer.analyze(trace, model);
    }
}
