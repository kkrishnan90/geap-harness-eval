package com.gridline.telemetry.ingest;

import static testkit.Assert.*;

import com.gridline.telemetry.model.Quality;
import com.gridline.telemetry.model.Reading;
import com.gridline.telemetry.units.UnitConverter;
import java.util.ArrayList;
import java.util.List;
import testkit.Test;

public class IngestParsersTest {
    @Test
    public void csvLineWithUnitConversion() throws Exception {
        Reading r = new CsvReadingParser().parseLine("SUB12-F04,2026-03-01T10:15:00Z,1.25,MW,G");
        assertEquals("SUB12-F04", r.feederId());
        assertEquals(1772360100000L, r.timestampMillis());
        assertEquals(1250.0, r.valueKw(), 1e-9, "kW");
        assertEquals(Quality.GOOD, r.quality());
    }

    @Test
    public void csvParseAllSkipsHeaderCommentsAndCollectsRejects() {
        List<ParseException> rejects = new ArrayList<>();
        List<Reading> rs = new CsvReadingParser().parseAll(List.of(
            "feeder_id,timestamp,value,unit,quality",
            "# exported by historian 7.2",
            "",
            "SUB12-F04,2026-03-01T10:15:00Z,800,kW,S",
            "SUB12-F04,yesterday,800,kW,G",
            "SUB12-F05,2026-03-01T10:15:00Z,-120000,W,GOOD",
            "SUB12-F05,2026-03-01T10:15:00Z,1,parsec,G"), rejects);
        assertEquals(2, rs.size());
        assertEquals(-120.0, rs.get(1).valueKw(), 1e-9, "W -> kW");
        assertEquals(2, rejects.size());
    }

    @Test
    public void scadaRoundTrip() throws Exception {
        String f = ScadaFrameParser.frame("SUB03-F01", 1772360100000L, 431.5, "S");
        Reading r = new ScadaFrameParser().parse(f);
        assertEquals("SUB03-F01", r.feederId());
        assertEquals(431.5, r.valueKw(), 1e-9, "kW");
        assertEquals(Quality.SUSPECT, r.quality());
    }

    @Test
    public void scadaRejectsCorruptFrames() {
        ScadaFrameParser p = new ScadaFrameParser();
        String good = ScadaFrameParser.frame("SUB03-F01", 1L, 2.0, "G");
        String flipped = good.replace("2.0", "3.0");
        assertThrows(ParseException.class, () -> p.parse(flipped));
        assertThrows(ParseException.class, () -> p.parse(good.substring(0, good.length() - 3)));
        assertThrows(ParseException.class, () -> p.parse("MODBUS|1|x"));
        String v2 = "SCADA|2|SUB03-F01|1|2.0|G";
        assertThrows(ParseException.class, () -> p.parse(v2 + "*" + String.format("%02X", ScadaFrameParser.checksum(v2))));
    }

    @Test
    public void unitConverter() {
        assertEquals(0.5, UnitConverter.toKw(500, "W"), 1e-12, "W");
        assertEquals(2000.0, UnitConverter.toKw(2, "mw"), 1e-12, "MW");
        assertThrows(IllegalArgumentException.class, () -> UnitConverter.toKw(1, "hp"));
    }
}
