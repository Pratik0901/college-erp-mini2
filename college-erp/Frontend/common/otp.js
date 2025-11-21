// Requires smtpjs <script src="https://smtpjs.com/v3/smtp.js"></script> in page.
function sendOTP(role){
  const emailEl = document.getElementById('email');
  const otpBox = document.getElementsByClassName('otpverify')[0];
  if(!emailEl || !emailEl.value){ alert('Enter email'); return; }
  const email = emailEl.value.trim();
  const otp_val = Math.floor(1000 + Math.random() * 9000);
  const subjMap = { admin:'Admin Password Reset OTP', staff:'Staff Password Reset OTP', student:'Student Password Reset OTP' };
  const subject = subjMap[role] || 'Password Reset OTP';
  const emailbody = `<h2>${subject}</h2><p>Your OTP: <b>${otp_val}</b></p>`;
  Email.send({
    SecureToken: "00c5a91d-97f4-47ef-a383-eb3b241ea9d0",
    To: email,
    From: "pratikmg09@gmail.com",
    Subject: subject,
    Body: emailbody
  }).then(msg=>{
    if(msg==="OK"){
      alert("OTP sent to " + email);
      if(otpBox) otpBox.style.display="flex";
      const otp_inp = document.getElementById('otp_inp');
      const otp_btn = document.getElementById('otp-btn');
      if(otp_btn){
        otp_btn.onclick = () => {
          if(otp_inp && otp_inp.value == otp_val){
            alert("OTP verified");
            location.href = `../common/new-password.html?role=${encodeURIComponent(role||'user')}&email=${encodeURIComponent(email)}`;
          } else {
            alert("Invalid OTP");
          }
        };
      }
    } else {
      alert("Failed to send email");
    }
  }).catch(()=>alert("Error sending OTP"));
}
