package Dumblewindows.javafx.dumblefx.controllers;

import Dumblewindows.javafx.dumblefx.API.ApiClient;
import Dumblewindows.javafx.dumblefx.i18n.I18n;
import Dumblewindows.javafx.dumblefx.Modelos.Alumno;
import Dumblewindows.javafx.dumblefx.Modelos.Matricula;
import Dumblewindows.javafx.dumblefx.assets.StudentIdPreview;
import Dumblewindows.javafx.dumblefx.assets.InputValidation;
import javafx.beans.property.SimpleStringProperty;
import javafx.collections.FXCollections;
import javafx.concurrent.Task;
import javafx.fxml.FXML;
import javafx.scene.control.*;
import javafx.scene.layout.VBox;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.function.Consumer;

/**
 * Controlador compartido por las pantallas de consulta, alta, actualización y eliminación.
 * Cada FXML inyecta solamente los controles que utiliza; por ello algunos campos pueden ser null.
 * Las llamadas a la API se ejecutan en tareas de fondo y sus resultados se aplican en el hilo JavaFX.
 *
 * @author Alain Paunero
 */
public final class StudentController {
    /**
     * Panel que se deshabilita temporalmente durante las peticiones.
     */
    @FXML private VBox operationPane;
    /**
     * Campos opcionales de identificador, filtros y datos de matrícula, según el FXML cargado.
     */
    @FXML private TextField idField, searchField, houseFilterField, limitField, nameField, surnameField, houseField;
    /**
     * Calendario de nacimiento, presente en las pantallas de alta y actualización.
     */
    @FXML private DatePicker birthDatePicker;
    /**
     * Etiquetas de estado y detalle, presentes según la operación.
     */
    @FXML private Label status, result;
    /**
     * Tabla de resultados de la consulta por datos.
     */
    @FXML private TableView<Alumno> table;
    /**
     * Columnas de identificador, nombre, apellidos, casa y nacimiento de la tabla.
     */
    @FXML private TableColumn<Alumno, String> idColumn, nameColumn, surnameColumn, houseColumn, birthColumn;
    /**
     * Cliente de acceso a la API utilizado por las tareas de fondo.
     */
    private final ApiClient api = new ApiClient();
    /**
     * ID cargado y seleccionado antes de actualizar o eliminar; null si no hay registro preparado.
     */
    private String loadedId;

    /**
     * Prepara validadores, calendario y columnas de los controles presentes en el FXML.
     * En el alta genera una vista previa del ID; el calendario impide fechas futuras.
     */
    @FXML private void initialize() {
        validateInput(nameField, false);
        validateInput(surnameField, false);
        validateInput(searchField, false);
        if (idField != null && idField.isEditable()) validateInput(idField, true);
        if (birthDatePicker != null) {
            birthDatePicker.setEditable(false);
            birthDatePicker.setDayCellFactory(picker -> new DateCell() {
                /**
                 * Deshabilita celdas vacías y fechas posteriores a hoy.
                 * @param date fecha representada por la celda
                 * @param empty true si la celda no contiene una fecha
                 */
                @Override public void updateItem(LocalDate date, boolean empty) {
                    super.updateItem(date, empty);
                    setDisable(empty || date == null || date.isAfter(LocalDate.now()));
                }
            });
        }
        // El FXML de alta distingue su modo mediante el ID no editable.
        if (surnameField != null && !idField.isEditable()) {
            idField.setEditable(false);
            idField.setDisable(true);
            // Se mantiene la casa Central, también al cargar datos para actualizar.
            houseField.setText("Central");

            nameField.textProperty().addListener((observable, previous, current) -> previewId());
            surnameField.textProperty().addListener((observable, previous, current) -> previewId());
            houseField.textProperty().addListener((observable, previous, current) -> previewId());
            previewId();
        }
        if (table == null) return;
        idColumn.setCellValueFactory(cell -> new SimpleStringProperty(cell.getValue().getId()));
        nameColumn.setCellValueFactory(cell -> new SimpleStringProperty(cell.getValue().getNombre()));
        surnameColumn.setCellValueFactory(cell -> new SimpleStringProperty(cell.getValue().getApellidos()));
        houseColumn.setCellValueFactory(cell -> new SimpleStringProperty(cell.getValue().getCasa()));
        birthColumn.setCellValueFactory(cell -> new SimpleStringProperty(cell.getValue().getNacimiento()));
        Label placeholder = new Label();
        I18n.message(placeholder.textProperty(), "status.empty");
        table.setPlaceholder(placeholder);
    }

    /**
     * Instala un filtro de entrada y convierte los IDs escritos a mayúsculas.
     * Ignora controles ausentes y rechaza cambios no válidos mostrando una explicación.
     *
     * @param field campo de texto, o null si no existe en la vista
     * @param identifier true para aplicar las reglas de ID; false para nombres
     */
    private void validateInput(TextField field, boolean identifier) {
        if (field == null) return;
        field.setTextFormatter(new TextFormatter<String>(change -> {
            if (identifier && change.isContentChange()) {
                change.setText(change.getText().toUpperCase(java.util.Locale.ROOT));
            }
            String value = change.getControlNewText();
            boolean valid = identifier ? InputValidation.allowsIdInput(value) : InputValidation.allowsNameInput(value);
            if (valid) return change;
            I18n.message(status.textProperty(), identifier ? "validation.id" : "validation.nameCharacters");
            return null;
        }));
    }

    /**
     * Recalcula la vista previa del identificador usando casa, nombre y apellidos.
     */
    private void previewId() {
        idField.setText(StudentIdPreview.generate(houseField.getText(), nameField.getText(), surnameField.getText()));
    }

    /**
     * Valida el ID y consulta coincidencias, permitiendo elegir el estudiante que se muestra.
     */
    @FXML private void findId() {
        String id = parsedId();
        if (id != null) run(() -> api.findById(id), alumnos -> selectStudent(alumnos, "selection.view", this::describe));
    }

    /**
     * Valida filtros y límite, consulta la API y reemplaza los resultados de la tabla.
     */
    @FXML private void search() {
        int limit;
        try {
            limit = Integer.parseInt(limitField.getText().trim());
            if (limit < 1 || limit > 100) throw new NumberFormatException();
        } catch (NumberFormatException error) {
            I18n.message(status.textProperty(), "validation.limit");
            return;
        }
        String name = searchField.getText().trim();
        if (!name.isEmpty() && !InputValidation.isName(name)) {
            I18n.message(status.textProperty(), "validation.nameCharacters");
            return;
        }
        String house = houseFilterField.getText().trim();
        run(() -> api.search(name, house, limit), alumnos -> {
            table.setItems(FXCollections.observableArrayList(alumnos));
            I18n.message(status.textProperty(), "status.results", alumnos.size());
        });
    }

    /**
     * Valida el formulario, crea la matrícula y muestra el ID definitivo recibido.
     * Tras el éxito limpia nombre, apellidos y fecha, y restablece la casa Central.
     */
    @FXML private void create() {
        Matricula value = form(null);
        if (value == null) return;
        run(() -> api.create(value), created -> {
            nameField.clear();
            surnameField.clear();
            // Se mantiene la casa Central, también al cargar datos para actualizar.
            houseField.setText("Central");
            birthDatePicker.setValue(null);
            idField.setText(created.studentId());
            I18n.message(status.textProperty(), "status.created", created.studentId());
        });
    }

    /**
     * Carga y selecciona el estudiante a modificar, conservando Central en el campo casa.
     * Si la fecha recibida no es válida, avisa y no habilita el registro como cargado.
     */
    @FXML private void loadForUpdate() {
        String id = parsedId();
        if (id == null) return;
        loadedId = null;
        run(() -> api.findById(id), alumnos -> selectStudent(alumnos, "selection.update", alumno -> {
            nameField.setText(alumno.getNombre());
            surnameField.setText(alumno.getApellidos());
            // Se mantiene la casa Central, también al cargar datos para actualizar.
            houseField.setText("Central");
            String birth = alumno.getNacimiento();
            try {
                birthDatePicker.setValue(birth == null || birth.isBlank() ? null : InputValidation.parseBirthDate(birth));
            } catch (DateTimeParseException error) {
                birthDatePicker.setValue(null);
                I18n.message(status.textProperty(), "validation.date");
                return;
            }
            loadedId = alumno.getId();
            idField.setText(loadedId);
            I18n.message(status.textProperty(), "status.loaded");
        }));
    }

    /**
     * Actualiza únicamente el ID que se cargó y seleccionó previamente.
     * Valida el formulario y conserva el identificador devuelto por la API.
     */
    @FXML private void update() {
        String id = parsedId();
        if (id == null) return;
        if (!id.equals(loadedId)) {
            I18n.message(status.textProperty(), "validation.load");
            return;
        }
        Matricula value = form(id);
        if (value != null) run(() -> api.update(id, value), updated -> {
            loadedId = updated.studentId();
            idField.setText(loadedId);
            I18n.message(status.textProperty(), "status.updated", updated.studentId());
        });
    }

    /**
     * Limpia la selección anterior y carga el estudiante cuyos datos se van a eliminar.
     */
    @FXML private void loadForDelete() {
        String id = parsedId();
        loadedId = null;
        result.textProperty().unbind();
        result.setText("");
        if (id != null) run(() -> api.findById(id), alumnos -> selectStudent(alumnos, "selection.delete", alumno -> {
            loadedId = alumno.getId();
            idField.setText(loadedId);
            describe(alumno);
        }));
    }

    /**
     * Exige cargar el registro y confirmar la eliminación antes de llamar a la API.
     * Al completarse borra la selección y los detalles mostrados.
     */
    @FXML private void delete() {
        String id = parsedId();
        if (id == null) return;
        if (!id.equals(loadedId)) {
            I18n.message(status.textProperty(), "validation.loadDelete");
            return;
        }
        ButtonType cancel = new ButtonType(I18n.text("action.cancel"), ButtonBar.ButtonData.CANCEL_CLOSE);
        ButtonType confirm = new ButtonType(I18n.text("action.confirm"), ButtonBar.ButtonData.OK_DONE);
        Alert alert = new Alert(Alert.AlertType.CONFIRMATION, "", cancel, confirm);
        I18n.tooltip((Button) alert.getDialogPane().lookupButton(cancel), "tooltip.cancelDelete");
        I18n.tooltip((Button) alert.getDialogPane().lookupButton(confirm), "tooltip.confirmDelete");
        I18n.message(alert.titleProperty(), "delete.header");
        I18n.message(alert.headerTextProperty(), "delete.header");
        I18n.message(alert.contentTextProperty(), "delete.confirm", id);
        alert.initOwner(operationPane.getScene().getWindow());
        if (alert.showAndWait().orElse(cancel) != confirm) return;
        run(() -> { api.delete(id); return null; }, ignored -> {
            loadedId = null;
            result.textProperty().unbind(); result.setText(""); I18n.message(status.textProperty(), "status.deleted");
        });
    }

    /**
     * Lee el identificador, elimina espacios exteriores y valida su formato.
     *
     * @return ID válido, o null tras mostrar un mensaje de validación
     */
    private String parsedId() {
        String id = idField.getText().trim();
        if (!InputValidation.isId(id)) {
            I18n.message(status.textProperty(), "validation.id");
            return null;
        }
        return id;
    }

    /**
     * Valida nombres, casa y fecha antes de construir los datos de matrícula.
     * En el alta usa Central si la casa está vacía; las fechas ausentes se envían como null.
     *
     * @param id identificador del estudiante; null al construir los datos de alta
     * @return matrícula preparada, o null si falla alguna validación
     */
    private Matricula form(String id) {
        String name = nameField.getText().trim();
        String surname = surnameField.getText().trim();
        String house = houseField.getText().trim();
        if (id == null && house.isBlank()) house = "Central";
        if (!InputValidation.isName(surname)) {
            I18n.message(status.textProperty(), "validation.surname");
            return null;
        }
        LocalDate birth = birthDatePicker.getValue();
        if (!InputValidation.isName(name)) {
            I18n.message(status.textProperty(), "validation.name");
            return null;
        }
        if (house.length() > 80) {
            I18n.message(status.textProperty(), "validation.house");
            return null;
        }
        if (birth != null && birth.isAfter(LocalDate.now())) {
            I18n.message(status.textProperty(), "validation.dateFuture");
            return null;
        }
        return new Matricula(id, name, surname, house.isBlank() ? null : house, birth == null ? null : birth.toString());
    }

    /**
     * Muestra los datos del estudiante mediante un mensaje traducido.
     *
     * @param alumno estudiante cuyos datos se presentan
     */
    private void describe(Alumno alumno) {
        I18n.message(result.textProperty(), "result.details", alumno.getId(), text(alumno.getNombre()),
                text(alumno.getApellidos()), text(alumno.getCasa()), text(alumno.getNacimiento()));
    }

    /**
     * Gestiona cero, una o varias coincidencias de consulta.
     * Para varias muestra un diálogo con selección obligatoria; cancelar no ejecuta el callback.
     *
     * @param alumnos coincidencias recibidas de la API
     * @param headerKey clave traducida del encabezado del diálogo
     * @param selected callback que recibe el estudiante elegido
     */
    private void selectStudent(List<Alumno> alumnos, String headerKey, Consumer<Alumno> selected) {
        if (alumnos.isEmpty()) {
            I18n.message(status.textProperty(), "status.empty");
            return;
        }
        if (alumnos.size() == 1) {
            selected.accept(alumnos.get(0));
            return;
        }
        Dialog<Alumno> dialog = new Dialog<>();
        dialog.initOwner(operationPane.getScene().getWindow());
        I18n.message(dialog.titleProperty(), "selection.title");
        I18n.message(dialog.headerTextProperty(), headerKey);
        TableView<Alumno> choices = new TableView<>(FXCollections.observableArrayList(alumnos));
        choices.getColumns().add(selectionColumn("field.id", Alumno::getId));
        choices.getColumns().add(selectionColumn("field.name", Alumno::getNombre));
        choices.getColumns().add(selectionColumn("field.surname", Alumno::getApellidos));
        choices.getColumns().add(selectionColumn("field.house", Alumno::getCasa));
        choices.getColumns().add(selectionColumn("field.birth", Alumno::getNacimiento));
        choices.setColumnResizePolicy(TableView.CONSTRAINED_RESIZE_POLICY);
        choices.setPrefSize(780, 300);
        dialog.getDialogPane().setContent(choices);
        ButtonType choose = new ButtonType(I18n.text("action.select"), ButtonBar.ButtonData.OK_DONE);
        ButtonType cancel = new ButtonType(I18n.text("action.cancel"), ButtonBar.ButtonData.CANCEL_CLOSE);
        dialog.getDialogPane().getButtonTypes().addAll(choose, cancel);
        I18n.tooltip((Button) dialog.getDialogPane().lookupButton(choose), "tooltip.select");
        I18n.tooltip((Button) dialog.getDialogPane().lookupButton(cancel), "tooltip.cancelSelection");
        dialog.getDialogPane().lookupButton(choose).disableProperty()
                .bind(choices.getSelectionModel().selectedItemProperty().isNull());
        dialog.setResizable(false);
        dialog.setResultConverter(button -> button == choose ? choices.getSelectionModel().getSelectedItem() : null);
        dialog.showAndWait().ifPresentOrElse(selected,
                () -> I18n.message(status.textProperty(), "status.cancelled"));
    }

    /**
     * Construye una columna traducida para la tabla del diálogo de selección.
     *
     * @param key clave del catálogo de traducciones
     * @param value función que obtiene el texto de cada estudiante
     * @return columna que presenta el valor extraído del estudiante
     */
    private TableColumn<Alumno, String> selectionColumn(String key, java.util.function.Function<Alumno, String> value) {
        TableColumn<Alumno, String> column = new TableColumn<>();
        I18n.message(column.textProperty(), key);
        column.setCellValueFactory(cell -> new SimpleStringProperty(text(value.apply(cell.getValue()))));
        return column;
    }

    /**
     * Sustituye valores ausentes por un guion de presentación.
     *
     * @param value valor que se valida, transforma o envía
     * @return valor original o raya si es null o está en blanco
     */
    private static String text(String value) { return value == null || value.isBlank() ? "—" : value; }

    /**
     * Ejecuta trabajo de API en un hilo daemon y bloquea el panel mientras dura la tarea.
     * Los callbacks de Task vuelven al hilo JavaFX: restauran el panel y muestran éxito o error.
     *
     * @param <T> tipo del resultado de la operación de fondo
     * @param work operación de fondo que puede lanzar una excepción
     * @param success callback de interfaz que recibe el resultado
     */
    private <T> void run(Callable<T> work, Consumer<T> success) {
        I18n.message(status.textProperty(), "status.connecting");
        operationPane.setDisable(true);
        Task<T> task = new Task<>() {
            /**
             * Ejecuta la operación fuera del hilo de interfaz.
             * @return resultado de la operación de API
             * @throws Exception si falla la operación de fondo
             */
            @Override protected T call() throws Exception { return work.call(); }
        };
        task.setOnSucceeded(event -> {
            operationPane.setDisable(false);
            I18n.message(status.textProperty(), "status.ready"); success.accept(task.getValue());
        });
        task.setOnFailed(event -> {
            operationPane.setDisable(false);
            I18n.message(status.textProperty(), "status.error", task.getException().getMessage());
        });
        Thread thread = new Thread(task, "dumblefx-api");
        thread.setDaemon(true); thread.start();
    }
}
