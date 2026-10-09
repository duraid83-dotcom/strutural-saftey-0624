import math
from flask import Flask, render_template, request

app = Flask(__name__, template_folder='.', static_folder='.')

@app.route('/', methods=['GET', 'POST'])
def index():
    results = None
    alarm = False
    
    if request.method == 'POST':
        try:
            # 1. Inputs
            P_kN = float(request.form.get('P', 0))       # Axial Force in kN
            L_m = float(request.form.get('L', 0))        # Length in m
            D_mm = float(request.form.get('D', 0))       # Diameter in mm
            E_GPa = float(request.form.get('E', 0))      # Modulus of Elasticity in GPa
            sigma_y = float(request.form.get('sigma_y', 0)) # Yield Strength in MPa

            # 2. Calculations
            P_N = P_kN * 1000.0                          # kN to N
            L_mm = L_m * 1000.0                          # m to mm
            E_MPa = E_GPa * 1000.0                       # GPa to MPa
            
            # Area A (mm^2)
            A = (math.pi / 4.0) * (D_mm ** 2)
            
            # Axial Stress sigma (MPa)
            sigma = P_N / A if A > 0 else 0
            
            # Axial Strain epsilon (mm/mm)
            epsilon = sigma / E_MPa if E_MPa > 0 else 0
            
            # Axial Deformation delta_L (mm)
            delta_L = epsilon * L_mm
            
            # 3. Warning Alarm Logic Check
            if abs(sigma) > sigma_y:
                alarm = True

            results = {
                'P': P_kN, 'L': L_m, 'D': D_mm, 'E': E_GPa, 'sigma_y': sigma_y,
                'A': round(A, 2),
                'sigma': round(sigma, 2),
                'epsilon': f"{epsilon:.6f}",
                'delta_L': round(delta_L, 4),
                'alarm': alarm
            }
        except Exception as e:
            results = None

    return render_template('index.html', results=results)

if __name__ == '__main__':
    app.run()
