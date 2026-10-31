from datetime import date

from mpi import PatientRecord

# Synthetic people only.
SMALL = [
    PatientRecord("R000001", "HOSP-A", "Thompson", "Grace", date(1984, 2, 9), "F", "N4 2AB", "07700900111"),
    PatientRecord("R000002", "GPNET", "Tompson", "Grace", date(1984, 2, 9), "F", "N4 2AB", ""),
    PatientRecord("R000003", "LAB", "Thompson", "G", None, "F", "", "+44 7700 900111"),
    PatientRecord("R000004", "HOSP-B", "Okafor", "Daniel", date(1971, 11, 30), "M", "N9 7QT", "07700900222"),
    PatientRecord("R000005", "HOSP-A", "Okafor", "Dan", date(1971, 11, 30), "M", "N9 7QT", "07700900222"),
    PatientRecord("R000006", "LAB", "Smith", "Olivia", date(1990, 5, 1), "F", "N1 1AA", ""),
    PatientRecord("R000007", "GPNET", "Smyth", "Oliver", date(1990, 5, 1), "M", "N2 2BB", ""),
]
