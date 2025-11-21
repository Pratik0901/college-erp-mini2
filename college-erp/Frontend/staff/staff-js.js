const USER_ID = 3;

async function loadDashboard() {
  try {
    const res = await fetch(`/api/staff/${USER_ID}/summary`);
    const data = await res.json();
    
    document.getElementById('totalCourses').textContent = data.total_courses;
    document.getElementById('totalStudents').textContent = data.total_students;
  } catch (e) {
    console.error('Error loading dashboard:', e);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', loadDashboard);
} else {
  loadDashboard();
}
