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
        <Box sx={{ width: '100%', overflowX: 'auto', display: 'block' }}>
          <Table size="small">
            <TableBody>
              {TAGS.map(tag => {
              let rawValue = meta?.[tag.key];
              let compareValue = compareTo && compareTo[tag.key];
              let highlight = false;
              // Robust comparison: if both are objects, compare as strings, otherwise direct comparison
              if (compareTo && compareTo.hasOwnProperty(tag.key)) {
                if (typeof rawValue === 'object' && typeof compareValue === 'object') {
                  highlight = JSON.stringify(rawValue) !== JSON.stringify(compareValue);
                } else {
                  highlight = String(rawValue ?? '') !== String(compareValue ?? '');
                }
              }
              // For display, normalize value as before
              let value = rawValue || '';
              if (value && typeof value === 'object') {
                if (value.Alphabetic) value = value.Alphabetic;
                else value = JSON.stringify(value);
              }
              return (
                <TableRow key={tag.key}>
                  <TableCell sx={{ fontWeight: 500 }}>{tag.label}</TableCell>
                  <TableCell>
                    <Box component="span" sx={highlight ? { color: 'success.main', fontWeight: 700 } : {}}>
                      {value}
                    </Box>
                  </TableCell>
                </TableRow>
              );
              })}
            </TableBody>
          </Table>
        </Box>
      </CardContent>
    </Card>
  );
}
