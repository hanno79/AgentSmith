"""
Author: rahn
Datum: 07.02.2026
Version: 1.0
Beschreibung: Python CLI Tool - Einstiegspunkt
"""
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="CLI Tool")
    parser.add_argument("--version", action="version", version="1.0.0")
    args = parser.parse_args()
    print("CLI Tool gestartet")

if __name__ == "__main__":
    main()
