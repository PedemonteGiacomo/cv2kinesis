
import React, { useEffect, useRef } from 'react';
import cornerstone from 'cornerstone-core';
import cornerstoneWADOImageLoader from 'cornerstone-wado-image-loader';


import dicomParser from 'dicom-parser';

cornerstoneWADOImageLoader.external.cornerstone = cornerstone;
cornerstoneWADOImageLoader.external.dicomParser = dicomParser;

export default function DicomViewer({ url }) {
  const divRef = useRef();

  useEffect(() => {
    if (!url || !divRef.current) return;

    cornerstone.enable(divRef.current);
    const imageId = 'wadouri:' + url;
    cornerstone.loadImage(imageId).then(image => {
      cornerstone.displayImage(divRef.current, image);
    });

    return () => {
      cornerstone.disable(divRef.current);
    };
  }, [url]);

  return (
    <div
      ref={divRef}
       style={{ width: 512, height: 512, background: '#222', cursor: 'crosshair' }}
      tabIndex={0}
    />
  );
}
