"""
CSV/Excel to NEXUS/TNT Converter Service

Converts morphological matrices from CSV/Excel files into NEXUS (for discrete/morphological data)
or TNT (for continuous/numeric data) formats.

Features:
- Automatically detects whether data is morphological (symbolic) or numeric
- Converts "NA" to "-" for inapplicable data, handles "?" for missing data
- Generates CHARSTATELABELS for NEXUS and CNAMES for TNT
- Issues warnings if data appears mixed (part symbolic, part numeric)
- Returns formatted output as strings
"""

import pandas as pd
import re
from io import BytesIO, StringIO
from typing import Union, Tuple, Optional
from .exceptions import log_execution, handle_exceptions


class CSVConverterService:
    """Service for converting CSV/Excel files to NEXUS or TNT format."""
    
    def __init__(self):
        pass
    
    @log_execution
    @handle_exceptions
    def load_matrix(self, file: Union[bytes, BytesIO, str], file_extension: str) -> pd.DataFrame:
        """
        Load matrix from file into pandas DataFrame.
        
        Args:
            file: File content as bytes, BytesIO, or file path string
            file_extension: File extension (.csv or .xlsx)
            
        Returns:
            pd.DataFrame: Loaded matrix data
        """
        try:
            if file_extension.lower() == '.xlsx':
                if isinstance(file, str):
                    return pd.read_excel(
                        file,
                        header=None,
                        engine="openpyxl",
                        keep_default_na=False,
                        na_values=[""]
                    )
                elif isinstance(file, bytes):
                    return pd.read_excel(
                        BytesIO(file),
                        header=None,
                        engine="openpyxl",
                        keep_default_na=False,
                        na_values=[""]
                    )
                else:  # BytesIO
                    file.seek(0)
                    return pd.read_excel(
                        file,
                        header=None,
                        engine="openpyxl",
                        keep_default_na=False,
                        na_values=[""]
                    )
            elif file_extension.lower() == '.csv':
                if isinstance(file, str):
                    return pd.read_csv(
                        file,
                        header=None,
                        keep_default_na=False,
                        na_values=[""]
                    )
                elif isinstance(file, bytes):
                    return pd.read_csv(
                        BytesIO(file),
                        header=None,
                        keep_default_na=False,
                        na_values=[""]
                    )
                else:  # BytesIO or StringIO
                    file.seek(0)
                    return pd.read_csv(
                        file,
                        header=None,
                        keep_default_na=False,
                        na_values=[""]
                    )
            else:
                raise ValueError(f"Unsupported file extension: {file_extension}")
        except Exception as e:
            raise ValueError(f"Error reading input file: {str(e)}")
    
    @log_execution
    def detect_mode(self, df: pd.DataFrame) -> Tuple[str, float, Optional[str]]:
        """
        Determine if the matrix is morphological (standard) or numeric.
        
        Args:
            df: DataFrame containing the matrix data
            
        Returns:
            Tuple of (mode, ratio, warning_message)
            - mode: 'standard' or 'numeric'
            - ratio: Ratio of cells with state label information
            - warning_message: Optional warning if mixed format detected
        """
        if df.shape[0] >= 2:
            row = df.iloc[1, 1:]
            non_empty = row.dropna()
            text_like = non_empty.astype(str).str.contains(r"[:;]").sum()
            ratio = text_like / max(len(non_empty), 1)
            
            warning_message = None
            if 0.25 < ratio < 0.75:
                warning_message = "Mixed-format warning: Some characters appear standard, others numeric. You may wish to split the dataset or double-check the format."
            
            if ratio > 0.5:
                return 'standard', ratio, warning_message
            else:
                return 'numeric', ratio, warning_message
        return 'numeric', 0.0, None
    
    @staticmethod
    def clean_cell(x):
        """Clean cell values for phylogenetic data format."""
        if pd.isna(x):
            return '?'
        x_str = str(x).strip()
        if x_str == '?':
            return '?'
        elif x_str.upper() == 'NA':
            return '-'
        return x_str
    
    @staticmethod
    def quote(s, force=False):
        """Add quotes to strings if needed for NEXUS format."""
        s = str(s).strip()
        # Escape single quotes by doubling them (NEXUS standard)
        if "'" in s:
            s = s.replace("'", "''")
            force = True
        if force or not s.isidentifier() or any(c in s for c in " ,:;()[]{}\"/-\\") or (s and s[0].isdigit()):
            return f"'{s}'"
        return s
    
    @log_execution
    @handle_exceptions
    def generate_tnt(self, taxa: pd.Series, matrix: pd.DataFrame, char_names: pd.Series) -> str:
        """
        Generate TNT format output for numeric/continuous data.
        
        Args:
            taxa: Series of taxon names
            matrix: DataFrame of character data
            char_names: Series of character names
            
        Returns:
            str: TNT formatted output
        """
        ntax = len(taxa)
        nchar = matrix.shape[1]
        tnt = []
        
        tnt.append("xread\n")
        tnt.append(f"{nchar} {ntax}\n")
        tnt.append("&[cont]\n")
        
        for i in range(ntax):
            taxon = taxa.iloc[i].replace("_", " ")
            row = ' '.join(matrix.iloc[i].tolist())
            tnt.append(f"{self.quote(taxon, force=True)} {row}\n")
        tnt.append(";\n")
        
        tnt.append("cnames\n")
        for i, cname in enumerate(char_names):
            clean = str(cname).strip().replace(" ", "_")
            tnt.append(f"{{ {i} {clean};\n")
        tnt.append(";\n")
        
        return ''.join(tnt)
    
    @log_execution
    @handle_exceptions
    def generate_nexus(self, taxa: pd.Series, matrix: pd.DataFrame, 
                      char_names: pd.Series, state_labels: Optional[pd.Series]) -> str:
        """
        Generate NEXUS format output for morphological/discrete data.
        
        Args:
            taxa: Series of taxon names
            matrix: DataFrame of character data
            char_names: Series of character names
            state_labels: Optional series of state label information
            
        Returns:
            str: NEXUS formatted output
        """
        ntax = len(taxa)
        nchar = matrix.shape[1]
        nexus = []
        
        nexus.append("#NEXUS\n\nBEGIN DATA;\n")
        nexus.append(f"  DIMENSIONS NTAX={ntax} NCHAR={nchar};\n")
        nexus.append("  FORMAT DATATYPE=STANDARD MISSING=? GAP=- SYMBOLS=\"0123456789\";\n")
        
        nexus.append("  CHARSTATELABELS\n")
        for i, cname in enumerate(char_names, start=1):
            qname = self.quote(cname)
            state_str = ""
            if state_labels is not None and i - 1 < len(state_labels):
                raw = state_labels.iloc[i - 1]
                if pd.notna(raw) and str(raw).strip():
                    states = []
                    raw_str = str(raw).strip()
                    # Handle different separators: semicolon, comma, or slash
                    if ';' in raw_str:
                        parts = raw_str.split(';')
                    elif ',' in raw_str:
                        parts = raw_str.split(',')
                    elif '/' in raw_str:
                        parts = raw_str.split('/')
                    else:
                        parts = [raw_str]
                    
                    for s in parts:
                        s = s.strip()
                        if not s:
                            continue
                        # Handle format like "0:StateName" or "0: StateName"
                        if ':' in s:
                            prefix, val = s.split(':', 1)
                            prefix = prefix.strip()
                            val = val.strip()
                            if prefix.isdigit():
                                s = val
                        # Strip trailing patterns like "Red (0)" or "State(0)"
                        match = re.match(r'^(.*?)\s*\(\s*\d+\s*\)$', s)
                        if match:
                            s = match.group(1).strip()
                        if s and s not in ['NA', 'na', '?', '-']:
                            states.append(self.quote(s))
                    if states:
                        state_str = " / " + ' '.join(states)
            comma = "," if i < len(char_names) else ""
            nexus.append(f"    {i} {qname}{state_str}{comma}\n")
        nexus.append("  ;\n\n")
        
        nexus.append("  MATRIX\n")
        for i in range(ntax):
            taxon = self.quote(taxa.iloc[i].replace(" ", "_"), force=True)
            row = ''.join([
                f"({val.replace('&', ' ')})" if '&' in val else val 
                for val in matrix.iloc[i].tolist()
            ])
            nexus.append(f"{taxon:<20} {row}\n")
        nexus.append("  ;\nEND;\n")
        
        return ''.join(nexus)
    
    @log_execution
    @handle_exceptions
    def convert(self, file: Union[bytes, BytesIO, str], file_extension: str) -> dict:
        """
        Main conversion method - converts CSV/Excel to NEXUS or TNT format.
        
        Args:
            file: File content or path
            file_extension: File extension (.csv or .xlsx)
            
        Returns:
            dict containing:
                - format: 'nexus' or 'tnt'
                - content: Formatted output string
                - mode: 'standard' or 'numeric'
                - ntax: Number of taxa
                - nchar: Number of characters
                - detection_ratio: Ratio used for mode detection
                - warnings: List of warning messages
        """
        # Load the matrix
        df = self.load_matrix(file, file_extension)
        
        # Detect mode
        mode, ratio, warning = self.detect_mode(df)
        warnings = []
        if warning:
            warnings.append(warning)
        
        # Parse matrix structure based on mode
        char_names_row = 0
        state_labels_row = 1 if mode == 'standard' else None
        taxa_start_row = 2 if mode == 'standard' else 1
        
        char_names = df.iloc[char_names_row, 1:]
        state_labels = None if state_labels_row is None else df.iloc[state_labels_row, 1:]
        taxa = df.iloc[taxa_start_row:, 0].astype(str).str.strip()
        matrix = df.iloc[taxa_start_row:, 1:].applymap(self.clean_cell)
        
        # Filter out empty taxa
        mask = taxa != ''
        taxa = taxa[mask]
        matrix = matrix[mask]
        
        if len(taxa) == 0 or matrix.shape[1] == 0:
            raise ValueError("No taxa or characters found in the matrix")
        
        # Check for polymorphic characters in numeric mode
        if mode == 'numeric':
            if matrix.applymap(lambda x: isinstance(x, str) and '&' in x).any().any():
                warnings.append(
                    "Polymorphic states (e.g., '0&1') detected in numeric mode. "
                    "This may indicate that your file contains mixed character types."
                )
        
        # Generate output
        if mode == 'numeric':
            content = self.generate_tnt(taxa, matrix, char_names)
            output_format = 'tnt'
        else:
            content = self.generate_nexus(taxa, matrix, char_names, state_labels)
            output_format = 'nexus'
        
        return {
            'format': output_format,
            'content': content,
            'mode': mode,
            'ntax': len(taxa),
            'nchar': matrix.shape[1],
            'detection_ratio': ratio,
            'warnings': warnings
        }
