async function loadDashboard() {
  try {
    const res = await fetch('/api/admin/summary');
    const data = await res.json();
    
    document.getElementById('totalStudents').textContent = data.total_students;
    document.getElementById('totalStaff').textContent = data.total_staff;
    document.getElementById('totalCourses').textContent = data.total_courses;
    document.getElementById('openComplaints').textContent = data.open_complaints;
  } catch (e) {
    console.error('Error loading dashboard:', e);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', loadDashboard);
} else {
  loadDashboard();
}
