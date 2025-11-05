import React from 'react';

function PlaceholderPage({ title }) {
  return (
    <div className="p-8 text-center">
      <h1 className="text-4xl font-bold">{title}</h1>
      <p className="mt-4 text-gray-500">Esta página está en construcción.</p>
    </div>
  );
}

export default PlaceholderPage;