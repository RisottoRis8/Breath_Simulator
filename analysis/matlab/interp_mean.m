%% Script: Interpolazione Singola + Visualizzazione Pressione Media
clear; clc; close all;

% --- PARAMETRI DI CONFIGURAZIONE ---
metodo_interp = 'pchip'; % Metodo: 'linear', 'pchip', 'spline', 'makima'
n_factor = 10;           % Moltiplicatore punti (n * numero campioni)

% --- SELEZIONE FILE ---
[file, path] = uigetfile('*.csv', 'Seleziona il file di misura CSV');
if isequal(file, 0), return; end
filename = fullfile(path, file);

% --- 1. LETTURA METADATI E ESTRAZIONE VALORE MEDIO ---
fprintf('\n==================================================\n');
fprintf('   RIEPILOGO METADATI: %s\n', file);
fprintf('==================================================\n');

% Leggiamo le prime righe per estrarre i metadati
meta_cells = readcell(filename, 'Range', 'A1:B6');
p_media_val = NaN; % Inizializzazione

for r = 1:size(meta_cells, 1)
    label = string(meta_cells{r,1});
    valore = meta_cells{r,2};
    
    if ~ismissing(label) && ~contains(label, '---')
        fprintf('  [INFO] %-30s : %s\n', label, string(valore));
        
        % Cerchiamo specificamente la riga della Pressione Media
        if contains(label, 'Pressione Media', 'IgnoreCase', true)
            if ischar(valore)
                p_media_val = str2double(valore);
            else
                p_media_val = valore;
            end
        end
    end
end
fprintf('==================================================\n\n');

% --- 2. CARICAMENTO DATI TABELLARI ---
opts = detectImportOptions(filename);
opts.VariableNamingRule = 'preserve';
opts.DataLine = 8;          
opts.VariableNamesLine = 7; 

data = readtable(filename, opts);
t_orig = data.Time_s;
p_orig = data.Pressure_Pa;

% Pulizia: rimozione duplicati temporali
[t, idx] = unique(t_orig);
p = p_orig(idx);

% --- 3. CALCOLO INTERPOLAZIONE ---
num_samples = length(t);
num_punti_interp = n_factor * num_samples;
t_interp = linspace(min(t), max(t), num_punti_interp);

p_interp = interp1(t, p, t_interp, metodo_interp);

% --- 4. GENERAZIONE GRAFICO ---
figure('Color', 'w', 'Name', ['Analisi Pressione: ' file]);
hold on;

% Plot 1: Dati Originali
plot(t, p, 'ko', 'MarkerFaceColor', [0.6 0.6 0.6], 'MarkerSize', 4, ...
    'DisplayName', 'Dati Sperimentali');

% Plot 2: Curva Interpolata
plot(t_interp, p_interp, 'b-', 'LineWidth', 2, ...
    'DisplayName', sprintf('Interpolazione %s (n=%d)', metodo_interp, n_factor));

% Plot 3: Linea Pressione Media (estratta dai metadati)
if ~isnan(p_media_val)
    yline(p_media_val, '--r', 'LineWidth', 1.5, ...
        'DisplayName', sprintf('Pressione Media Tabella (%.2f Pa)', p_media_val), ...
        'LabelVerticalAlignment', 'bottom', 'LabelHorizontalAlignment', 'right');
end

% Abbellimenti
grid on; box on;
xlabel('Tempo (s)');
ylabel('Pressione (Pa)');
title({['Analisi File: ' file], ...
       ['Metodo: ' metodo_interp ' | Punti: ' num2str(num_punti_interp)]});
legend('Location', 'best');

% Zoom automatico
axis tight;
fprintf('Valore Pressione Media utilizzato per il grafico: %.2f Pa\n', p_media_val);