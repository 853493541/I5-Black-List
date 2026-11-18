//! The page's and the card's Slint models, from [`super::rows`] and [`super::setup`].

use std::rc::Rc;

use slint::{ModelRc, SharedString, VecModel};

use super::rows::{self, SettingsState, SECTIONS};
use super::setup::{SetupModel, State, STEPS};
use crate::{RowData, SectionData, SettingsPreview, SetupWindow, StepData};

pub fn sections() -> ModelRc<SectionData> {
    let list: Vec<SectionData> =
        SECTIONS.iter().map(|(key, title, icon)| SectionData { key: (*key).into(), title: (*title).into(), icon: (*icon).into() }).collect();
    ModelRc::from(Rc::new(VecModel::from(list)))
}

/// One section's rows for `general-rows`, `help-rows` or `about-rows`.
pub fn rows(state: &SettingsState, section: &str) -> ModelRc<RowData> {
    let list: Vec<RowData> = rows::rows(state, section)
        .into_iter()
        .map(|row| RowData {
            section: row.section.into(),
            first: row.first,
            key: row.key.into(),
            name: row.name.into(),
            description: row.description.into(),
            kind: row.kind.into(),
            choices: ModelRc::from(Rc::new(VecModel::from(row.choices.into_iter().map(SharedString::from).collect::<Vec<_>>()))),
            value: row.value.into(),
            label: row.label.into(),
            note: row.note.into(),
            enabled: row.enabled,
        })
        .collect();
    ModelRc::from(Rc::new(VecModel::from(list)))
}

/// The page alone in its preview window.
pub fn show_settings(window: &SettingsPreview, state: &SettingsState) {
    window.set_sections(sections());
    window.set_general_rows(rows(state, "general"));
    window.set_help_rows(rows(state, "help"));
    window.set_about_rows(rows(state, "about"));
}

pub fn show_setup(window: &SetupWindow, model: &SetupModel) {
    window.set_state(
        match model.state {
            State::Ok => "ok",
            State::Failed => "failed",
            _ => "running",
        }
        .into(),
    );
    window.set_heading(model.heading().into());
    window.set_progress(model.value as f32);
    window.set_message(model.message.as_str().into());
    let steps: Vec<StepData> = STEPS
        .iter()
        .zip(&model.steps)
        .map(|(name, (step, note))| StepData { name: (*name).into(), state: step.name().into(), note: note.as_str().into() })
        .collect();
    window.set_steps(ModelRc::from(Rc::new(VecModel::from(steps))));
}
