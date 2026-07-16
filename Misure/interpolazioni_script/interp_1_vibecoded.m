%% Script Interpolazione con Estrazione Metadati
clear; clc; close all;

% --- PARAMETRI DI CONFIGURAZIONE ---
metodo_interpolazione = 'pchip'; 
n_factor = 10; % Punti interp = n_factor * campioni originali

% --- SELEZIONE FILE ---
[file, path] = uigetfile('*.csv', 'Seleziona il file di misura CSV');
if isequal(file, 0), return; end
filename = fullfile(path, file);

% --- 1. ESTRAZIONE METADATI (Riepilogo) ---
% Leggiamo le prime righe come testo puro
fid = fopen(filename, 'r');
fprintf('\n--- DATI RILEVATI DAL FILE ---\n');
for i = 1:5
    linea = fgetl(fid);
    if i > 1 % Saltiamo la riga 1 ("--- RIEPILOGO... ---") e stampiamo le altre
        % Sostituiamo la virgola del CSV con un tab o spazio per pulizia
        info_pulita = strrep(linea, ',', ': ');
        fprintf('%s\n', info_pulita);
    end
end
fclose(fid);
fprintf('------------------------------\n\n');

% --- 2. CARICAMENTO DATI TABELLARI ---
opts = detectImportOptions(filename);
opts.VariableNamingRule = 'preserve';
opts.DataLine = 8;          % I dati numerici iniziano alla riga 8
opts.VariableNamesLine = 7; % Intestazioni alla riga 7

data = readtable(filename, opts);
t = data.Time_s;
p = data.Pressure_Pa;

% Pulizia dati (rimozione duplicati temporali)
[t, idx] = unique(t);
p = p(idx);

% --- 3. CALCOLO INTERPOLAZIONE ---
num_samples = length(t);
num_punti_interp = n_factor * num_samples;
t_interp = linspace(min(t), max(t), num_punti_interp);

p_interp = interp1(t, p, t_interp, metodo_interpolazione);

% --- 4. VISUALIZZAZIONE ---
figure('Color', 'w');
plot(t, p, 'ko', 'MarkerFaceColor', 'r', 'DisplayName', 'Dati Originali');
hold on;
plot(t_interp, p_interp, 'b-', 'LineWidth', 1.5, 'DisplayName', ['Interpolazione ' metodo_interpolazione]);

grid on;
xlabel('Tempo (s)');
ylabel('Pressione (Pa)');
title(['File: ' file ' - Metodo: ' metodo_interpolazione]);
legend('Location', 'best');

% Output finale a terminale
fprintf('Analisi completata:\n');
fprintf('- Campioni originali: %d\n', num_samples);
fprintf('- Punti interpolati: %d\n', num_punti_interp);