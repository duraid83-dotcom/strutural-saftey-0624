/* Show only the inputs required for the selected structural case. */

const GROUPS = {
  axial: ["group-force", "group-area", "group-length", "group-e", "group-allowable"],
  tension: ["group-force", "group-area", "group-net-area", "group-length", "group-e", "group-allowable"],
  compression: ["group-force", "group-area", "group-length", "group-k", "group-inertia", "group-e", "group-allowable"],
  beam: ["group-beam-load", "group-beam-section", "group-length", "group-e", "group-allowable"],
  shear: ["group-shear-case", "group-force", "group-area", "group-allowable"],
};

const ALLOWABLE_LABELS = {
  axial: "Allowable stress σ_allow",
  tension: "Allowable tensile stress σ_allow",
  compression: "Allowable compressive stress σ_allow",
  beam: "Allowable bending stress σ_allow",
  shear: "Allowable shear stress τ_allow",
};

const FORCE_LABELS = {
  axial: "Applied axial load P",
  tension: "Tensile force P",
  compression: "Compressive load P",
  beam: "Concentrated load P (midspan)",
  shear: "Shear force V",
};

const TYPICAL_E = {
  steel: { value: "200", unit: "GPa" },
  aluminum: { value: "70", unit: "GPa" },
  concrete: { value: "30", unit: "GPa" },
  timber: { value: "12", unit: "GPa" },
};

function selectedType() {
  const el = document.getElementById("calc_type");
  return el ? el.value : "axial";
}

function setHidden(id, hidden) {
  const node = document.getElementById(id);
  if (node) node.classList.toggle("hidden", hidden);
}

function updateVisibleFields() {
  const type = selectedType();
  const show = new Set(GROUPS[type] || GROUPS.axial);
  document.querySelectorAll("[data-group]").forEach((node) => {
    node.classList.toggle("hidden", !show.has(node.dataset.group));
  });

  const allowLabel = document.getElementById("allowable-label-text");
  if (allowLabel) allowLabel.textContent = ALLOWABLE_LABELS[type];

  const forceLabel = document.getElementById("force-label-text");
  if (forceLabel) forceLabel.textContent = FORCE_LABELS[type];

  updateBeamLoadFields();
  updateBeamSectionFields();
  updateKFields();
}

function updateBeamLoadFields() {
  const type = selectedType();
  const loadType = document.getElementById("beam_load_type");
  const isBeam = type === "beam";
  const isPoint = !loadType || loadType.value === "point_midspan";
  setHidden("beam-point-wrap", !(isBeam && isPoint));
  setHidden("beam-udl-wrap", !(isBeam && !isPoint));
  // Point load uses the shared force group; keep it visible for point beams.
  if (isBeam) {
    const forceGroup = document.getElementById("group-force");
    if (forceGroup) forceGroup.classList.toggle("hidden", !isPoint);
  }
}

function updateBeamSectionFields() {
  const section = document.getElementById("beam_section");
  const isRect = !section || section.value === "rectangle";
  const isBeam = selectedType() === "beam";
  const isCustom = isBeam && !isRect;
  setHidden("beam-rect-wrap", !(isBeam && isRect));
  setHidden("beam-custom-wrap", !isCustom);
  setHidden("group-dim-unit", !isBeam);
  // Custom beam needs I; compression always needs I.
  const inertia = document.getElementById("group-inertia");
  if (inertia) {
    const showI = selectedType() === "compression" || isCustom;
    inertia.classList.toggle("hidden", !showI);
  }
}

function updateKFields() {
  const k = document.getElementById("k_factor");
  const isCompression = selectedType() === "compression";
  const isCustom = k && k.value === "custom";
  setHidden("k-custom-wrap", !(isCompression && isCustom));
}

function applyMaterialE() {
  const material = document.getElementById("material");
  const eInput = document.getElementById("youngs_modulus");
  const eUnit = document.getElementById("e_unit");
  if (!material || !eInput) return;
  const preset = TYPICAL_E[material.value];
  if (!preset) return;
  eInput.value = preset.value;
  if (eUnit) eUnit.value = preset.unit;
}

document.addEventListener("DOMContentLoaded", () => {
  const calc = document.getElementById("calc_type");
  const material = document.getElementById("material");
  const beamLoad = document.getElementById("beam_load_type");
  const beamSection = document.getElementById("beam_section");
  const kFactor = document.getElementById("k_factor");

  if (calc) calc.addEventListener("change", updateVisibleFields);
  if (beamLoad) beamLoad.addEventListener("change", updateBeamLoadFields);
  if (beamSection) beamSection.addEventListener("change", updateBeamSectionFields);
  if (kFactor) kFactor.addEventListener("change", updateKFields);
  if (material) material.addEventListener("change", applyMaterialE);

  const form = document.querySelector("form");
  if (form) {
    form.addEventListener("reset", () => {
      setTimeout(updateVisibleFields, 0);
    });
  }

  updateVisibleFields();
});
