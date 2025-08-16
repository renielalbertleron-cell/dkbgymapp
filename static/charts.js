window.onload = () => {
  const ctx = document.getElementById('salesChart');
  if (!ctx) return;
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['Mon','Tue','Wed','Thu','Fri'],
      datasets: [{
        label: 'Weekly Sales (₱)',
        data: [1200,900,1500,1300,1700],
        backgroundColor: 'rgba(0,123,255,0.6)'
      }]
    },
    options: { responsive: true, plugins: { legend: { display: false } } }
  });
};
 
