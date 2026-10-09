import io
import base64
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask, render_template, request

app = Flask(__name__, template_folder='.', static_folder='.')

@app.route('/', methods=['GET', 'POST'])
def index():
    results = None
    plot_url = None
    alarm = False
    
    if request.method == 'POST':
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

        # 4. Visualization (2D Deformation Plot)
        fig, ax = plt.subplots(figsize=(6, 2))
        ax.plot([0, L_mm], [0, 0], color='gray', linewidth=8, label='Original Member')
        ax.plot([0, L_mm + delta_L], [0.5, 0.5], color='red' if alarm else 'green', linewidth=8, 
                label=f'Deformed (dL = {delta_L:.2f} mm)')
        
        ax.set_ylim(-1, 1.5)
        ax.set_yticks([])
        ax.set_xlabel('Length (mm)')
        ax.set_title('Member Axial Deformation')
        ax.legend(loc='upper right')
        plt.tight_layout()

        # Convert plot to Base64 Image string
        img = io.BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)
        plot_url = base64.b64encode(img.getvalue()).decode()
        plt.close()

    return render_template('index.html', results=results, plot_url=plot_url)

if __name__ == '__main__':
    app.run()
