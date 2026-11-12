package Dumblewindows.javafx.dumblefx.assets;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.regex.Pattern;

/**
 * Reglas compartidas para validar identificadores y nombres.
 * Distingue la entrada parcial permitida durante la escritura del valor final válido.
 *
 * @author Alain Paunero
 */
public final class InputValidation {
    /**
     * Formato final del identificador, con sufijo numérico opcional.
     */
    private static final Pattern ID = Pattern.compile("[A-Za-z]{2}-[A-Za-z]{3}-[A-Za-z]{3}(?:-[0-9]{2})?");
    /**
     * Caracteres y longitud admitidos mientras se escribe un identificador.
     */
    private static final Pattern ID_INPUT = Pattern.compile("[A-Za-z0-9-]{0,13}");
    /**
     * Letras Unicode, marcas combinadas y espacios admitidos en nombres.
     */
    private static final Pattern NAME_INPUT = Pattern.compile("(?:\\p{L}\\p{M}*| )*");

    /**
     * Impide crear instancias de esta utilidad.
     */
    private InputValidation() { }

    /**
     * Valida un ID completo: dos letras, tres letras y tres letras separadas por guiones,
     * con un sufijo opcional de dos cifras.
     *
     * @param value valor que se valida, transforma o envía
     * @return true si el identificador completo tiene el formato esperado
     */
    public static boolean isId(String value) {
        return value != null && ID.matcher(value).matches();
    }

    /**
     * Permite letras ASCII, cifras y guiones hasta 13 caracteres durante la escritura.
     *
     * @param value valor que se valida, transforma o envía
     * @return true si se admite la entrada parcial, incluida la cadena vacía
     */
    public static boolean allowsIdInput(String value) {
        return value != null && ID_INPUT.matcher(value).matches();
    }

    /**
     * Permite letras Unicode, marcas combinadas y espacios hasta 200 caracteres.
     *
     * @param value valor que se valida, transforma o envía
     * @return true si se admite la entrada parcial del nombre
     */
    public static boolean allowsNameInput(String value) {
        return value != null && value.length() <= 200 && NAME_INPUT.matcher(value).matches();
    }

    /**
     * Exige un nombre no vacío ni compuesto únicamente por espacios, con caracteres permitidos.
     *
     * @param value valor que se valida, transforma o envía
     * @return true si el nombre está completo y es válido
     */
    public static boolean isName(String value) {
        return value != null && !value.isBlank() && allowsNameInput(value);
    }

    /**
     * Convierte la fecha recibida de la API, que llega como dd/MM/yyyy,
     * admitiendo también el formato ISO AAAA-MM-DD.
     *
     * @param value fecha recibida de la API, no vacía
     * @return fecha interpretada como calendario
     * @throws DateTimeParseException si no coincide con ninguno de los dos formatos
     */
    public static LocalDate parseBirthDate(String value) {
        try {
            return LocalDate.parse(value, DateTimeFormatter.ofPattern("dd/MM/yyyy"));
        } catch (DateTimeParseException error) {
            return LocalDate.parse(value);
        }
    }
}
