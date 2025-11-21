const USER_ID = 2; // This should come from login session

async function loadDashboard() {
  try {
    // Load summary
    const res = await fetch(`/api/student/${USER_ID}/summary`);
    const data = await res.json();
    
    document.getElementById('attendancePercent').textContent = data.attendance_percent + '%';
    document.getElementById('avgMarks').textContent = data.avg_marks;
    document.getElementById('pendingFees').textContent = '₹' + data.pending_fees;
    document.getElementById('attendanceDisplay').textContent = data.attendance_percent + '%';
    document.getElementById('feeAmount').textContent = data.pending_fees;
    
    // Load notifications
    const nRes = await fetch('/api/notifications?role=student');
    const notifications = await nRes.json();
    const nList = document.getElementById('notificationsList');
    if (notifications.length > 0) {
      nList.innerHTML = notifications.slice(0, 3).map(n => 
        `<div style="padding:8px 0;border-bottom:1px solid #eee">
          <strong>${n.title}</strong><br>
          <span class="small-muted">${n.body}</span>
        </div>`
      ).join('');
    } else {
      nList.innerHTML = '<p class="muted">No new notifications</p>';
    }
    
  } catch (e) {
    console.error('Error loading dashboard:', e);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', loadDashboard);
} else {
  loadDashboard();
}
