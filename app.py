"""
Flask web application for the Structural Safety Calculator.

Routes stay thin: they parse the HTTP request, call calculations.py, and
render templates. All engineering math lives in calculations.py.
"""

from flask import Flask, render_template, request

from calculations import CALC_TYPES, K_PRESETS, ValidationError, calculate

app = Flask(__name__)


@app.route("/")
def index():
    return render_template(
        "index.html",
        calc_types=CALC_TYPES,
        k_presets=K_PRESETS,
        errors={},
        form={},
    )


@app.route("/calculate", methods=["POST"])
def calculate_view():
    form = request.form
    try:
        result = calculate(form)
    except ValidationError as exc:
        return (
            render_template(
                "index.html",
                calc_types=CALC_TYPES,
                k_presets=K_PRESETS,
                errors=exc.errors,
                form=form,
            ),
            400,
        )
    return render_template("results.html", result=result)


if __name__ == "__main__":
    # Host 127.0.0.1 keeps the educational app on this machine only.
    app.run(host="127.0.0.1", port=5000, debug=True)
