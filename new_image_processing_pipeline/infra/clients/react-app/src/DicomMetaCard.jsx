import React from 'react';
import { Card, CardContent, Typography, Table, TableBody, TableRow, TableCell, Box } from '@mui/material';

// tags da mostrare
const TAGS = [
  { key: 'PatientID', label: 'Patient ID' },
  { key: 'PatientName', label: 'Patient Name' },
  { key: 'StudyInstanceUID', label: 'Study Instance UID' },
  { key: 'StudyDate', label: 'Study Date' },
  { key: 'StudyTime', label: 'Study Time' },
  { key: 'AccessionNumber', label: 'Accession Number' },
  { key: 'SeriesInstanceUID', label: 'Series Instance UID' },
  { key: 'SeriesNumber', label: 'Series Number' },
  { key: 'SeriesDescription', label: 'Series Description' },
  { key: 'Modality', label: 'Modality' },
  { key: 'ImageType', label: 'Image Type' },
  { key: 'ContentDate', label: 'Content Date' },
  { key: 'ContentTime', label: 'Content Time' },
  { key: 'ProtocolName', label: 'Protocol Name' },
];

export default function DicomMetaCard({ title, meta, compareTo }) {
  // compareTo: opzionale, se presente evidenzia i valori diversi
  return (
    <Card elevation={2} sx={{ mb: 2 }}>
      <CardContent>
        <Typography variant="subtitle1" fontWeight={600} gutterBottom>{title}</Typography>
        <Table size="small">
          <TableBody>
            {TAGS.map(tag => {
              let value = meta?.[tag.key] || '';
              // Se il valore è un oggetto (es. PatientName), converti in stringa leggibile
              if (value && typeof value === 'object') {
                // Caso PatientName: { Alphabetic: '...' }
                if (value.Alphabetic) value = value.Alphabetic;
                else value = JSON.stringify(value);
              }
              let highlight = false;
              let compareValue = compareTo && compareTo[tag.key];
              if (compareTo && value && value !== compareValue) highlight = true;
              return (
                <TableRow key={tag.key}>
                  <TableCell sx={{ fontWeight: 500 }}>{tag.label}</TableCell>
                  <TableCell>
                    <Box component="span" sx={highlight ? { color: 'success.main', fontWeight: 700 } : {}}>
                      {value}
                      {highlight && <Box component="span" sx={{ ml: 1, fontSize: '0.85em', color: 'primary.main' }}>(modificato)</Box>}
                    </Box>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
